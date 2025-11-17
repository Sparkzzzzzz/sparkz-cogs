import asyncio
import discord
import re
import time
from datetime import timedelta

from redbot.core import commands, checks, Config
from redbot.core.bot import Red


# ============================================================
# INTERVAL PARSER
# ============================================================
def parse_interval(text: str) -> int:
    """
    Convert strings like '5h6m12s' into seconds, e.g.:
    10s, 5m, 2h, 1h30m, 3h15s, 4h2m9s, etc.
    """
    pattern = r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$"
    m = re.fullmatch(pattern, text.strip().lower())

    if not m:
        raise ValueError(
            "Invalid interval format. Use formats like 5h, 10m, 30s, 1h30m, 2h6m10s."
        )

    h = int(m.group(1)) if m.group(1) else 0
    mi = int(m.group(2)) if m.group(2) else 0
    s = int(m.group(3)) if m.group(3) else 0

    total = h * 3600 + mi * 60 + s
    if total < 1:
        raise ValueError("Interval must be at least 1 second.")
    return total


class TaskPacket(commands.Cog):
    """Create groups of commands that execute in sequence, with optional repeated scheduling."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=762829303, force_registration=True
        )

        # Keep the same keys you used
        self.config.register_global(groups={})
        self.config.register_global(repeats={})
        # Format in config.repeats:
        # key = task_id
        # value = { group, interval, interval_raw, channel_id, next_run, state_repr, author_id, prefix }

        self.running_tasks = {}  # task_id -> asyncio task

        # restore on startup/reload
        asyncio.create_task(self._startup_load())

    # ============================================================
    # STARTUP: RESTORE TASKS
    # ============================================================
    async def _startup_load(self):
        await self.bot.wait_until_ready()
        stored = await self.config.repeats()
        # recreate tasks from stored config
        for task_id, data in stored.items():
            # minimal validation
            group = data.get("group")
            channel_id = data.get("channel_id")
            interval = data.get("interval")
            if not group or not channel_id or not interval:
                continue
            channel = self.bot.get_channel(channel_id)
            # only restore tasks whose channel is resolvable (skip otherwise)
            if channel is None:
                continue
            # create asyncio task
            loop_task = asyncio.create_task(self._repeat_loop(task_id, data))
            self.running_tasks[task_id] = loop_task

    # ============================================================
    # RUN BOT COMMAND - robust for both direct ctx and scheduled runs
    # ============================================================
    async def run_bot_command(
        self,
        ctx,
        command_string: str,
        *,
        channel: discord.abc.Messageable = None,
        state=None,
        author_obj=None,
        prefix=None,
    ):
        """
        Execute a command string as if typed by a user.
        Two modes:
         - direct mode: pass a real ctx (ctx is not None). Uses ctx.message._state etc.
         - scheduled mode: pass channel, state, author_obj, prefix; ctx should be None.
        """

        # Direct/invoked path: use the real ctx provided
        if ctx is not None:
            try:
                # Create a fake message using real ctx.message._state to ensure compatibility
                state = ctx.message._state
                fake_data = {
                    "id": ctx.message.id,
                    "type": 0,
                    "content": (ctx.prefix or "") + command_string,
                    "channel_id": ctx.channel.id,
                    "author": {
                        "id": ctx.author.id,
                        "username": ctx.author.name,
                        "avatar": ctx.author.avatar.key if ctx.author.avatar else None,
                        "discriminator": ctx.author.discriminator,
                        "public_flags": (
                            ctx.author.public_flags.value
                            if hasattr(ctx.author, "public_flags")
                            else 0
                        ),
                    },
                    "attachments": [],
                    "embeds": [],
                    "mentions": [],
                    "mention_roles": [],
                    "pinned": False,
                    "tts": False,
                    "timestamp": ctx.message.created_at.isoformat(),
                }
                fake_message = discord.Message(
                    state=state, channel=ctx.channel, data=fake_data
                )
                new_ctx = await self.bot.get_context(fake_message, cls=type(ctx))
                await self.bot.invoke(new_ctx)
                return
            except Exception:
                # fallback - try basic context invoke path
                try:
                    fake_msg = ctx.message
                    fake_msg.content = (ctx.prefix or "") + command_string
                    new_ctx = await self.bot.get_context(fake_msg, cls=type(ctx))
                    await self.bot.invoke(new_ctx)
                    return
                except Exception:
                    # swallow, will raise below if completely failing
                    pass

        # Scheduled path: build a message using the provided state / channel / author
        if state is None or channel is None or author_obj is None or prefix is None:
            raise RuntimeError(
                "Missing scheduling context when executing scheduled command."
            )

        # Ensure author_obj is a full User object
        if isinstance(author_obj, int):
            try:
                author = await self.bot.fetch_user(author_obj)
            except Exception:
                author = None
        else:
            author = author_obj

        author_data = {
            "id": author.id if author else 0,
            "username": getattr(author, "name", "Unknown") if author else "Unknown",
            "avatar": (
                author.avatar.key
                if (author and getattr(author, "avatar", None))
                else None
            ),
            "discriminator": (
                getattr(author, "discriminator", "0000") if author else "0000"
            ),
            "public_flags": (
                getattr(getattr(author, "public_flags", None), "value", 0)
                if author
                else 0
            ),
        }

        fake_data = {
            "id": int(time.time() * 1000) & 0xFFFFFFFF,
            "type": 0,
            "content": (prefix or "") + command_string,
            "channel_id": getattr(channel, "id", None),
            "author": author_data,
            "attachments": [],
            "embeds": [],
            "mentions": [],
            "mention_roles": [],
            "pinned": False,
            "tts": False,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
        }

        try:
            fake_message = discord.Message(state=state, channel=channel, data=fake_data)
            # Build a Context and invoke
            new_ctx = await self.bot.get_context(fake_message, cls=commands.Context)
            await self.bot.invoke(new_ctx)
        except Exception as exc:
            # If building Message or invoking fails, try a minimal fallback:
            try:
                # minimal fallback: create a simple object that resembles a message for get_context
                class SimpleMsg:
                    pass

                sm = SimpleMsg()
                sm._state = state
                sm.content = (prefix or "") + command_string
                sm.channel = channel
                sm.author = author
                sm.id = int(time.time() * 1000) & 0xFFFFFFFF
                sm.created_at = discord.utils.utcnow()
                new_ctx = await self.bot.get_context(sm, cls=commands.Context)
                await self.bot.invoke(new_ctx)
            except Exception:
                # Ultimately, if invocation fails, raise so callers can log or handle
                raise exc

    # ============================================================
    # BACKGROUND LOOP FOR EACH TASK
    # ============================================================
    async def _repeat_loop(self, task_id: str, data: dict):
        """
        Loop that runs commands for a given stored task_id.
        Uses stored state + channel_id + author_id + prefix saved in config entry.
        """

        group = data["group"]
        interval = data["interval"]
        channel_id = data["channel_id"]
        state_repr = data.get("state_repr")  # stored at creation (ctx.message._state)
        author_id = data.get("author_id")
        prefix = data.get("prefix", "")

        # Attempt to resolve a state object for Message construction
        state = state_repr if state_repr else getattr(self.bot, "_connection", None)

        while True:
            try:
                groups = await self.config.groups()
                if group not in groups:
                    # group removed -> stop loop and remove from config
                    try:
                        await self.config.repeats.clear_raw(task_id)
                    except Exception:
                        pass
                    break

                cmds = groups[group].copy()

                # resolve channel and author at runtime
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    # try fetching if not found in cache
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception:
                        # cannot resolve channel: skip this iteration, update next_run and sleep
                        data["next_run"] = time.time() + interval
                        await self.config.repeats.set_raw(task_id, value=data)
                        await asyncio.sleep(interval)
                        continue

                author = None
                if author_id:
                    try:
                        author = self.bot.get_user(
                            author_id
                        ) or await self.bot.fetch_user(author_id)
                    except Exception:
                        author = None

                for cmd in cmds:
                    try:
                        await self.run_bot_command(
                            None,
                            cmd,
                            channel=channel,
                            state=state,
                            author_obj=author,
                            prefix=prefix,
                        )
                    except Exception as exc:
                        # Attempt to log into the channel to indicate error
                        try:
                            await channel.send(f"❌ Error executing `{cmd}`:\n`{exc}`")
                        except Exception:
                            pass
                # schedule next run
                data["next_run"] = time.time() + interval
                await self.config.repeats.set_raw(task_id, value=data)

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return
            except Exception:
                # if loop experiences an unexpected error, wait briefly and continue
                try:
                    await asyncio.sleep(max(1, interval))
                except asyncio.CancelledError:
                    return

    # ============================================================
    # Helper to capture state and author when scheduling
    # ============================================================
    def _capture_state_and_prefix(self, ctx):
        """
        Returns a serializable representation of the state and prefix.
        We can't serialize the full state object; we'll store the state's object reference
        (non-serializable) for live reloads, but also keep fallback to bot._connection.
        """
        # Try to return the actual state object (works in-memory)
        state = getattr(ctx.message, "_state", None)
        return state

    # ============================================================
    # Construct a minimal fake ctx used by earlier code paths (kept for compatibility)
    # ============================================================
    def _fake_ctx(self):
        """Construct a minimal fake context-like object for legacy calls."""

        class Dummy:
            pass

        d = Dummy()
        # Use the bot's connection as fallback
        d.message = type(
            "FakeMsg",
            (),
            {
                "_state": getattr(self.bot, "_connection", None),
                "created_at": discord.utils.utcnow(),
            },
        )
        d.prefix = "."
        d.author = self.bot.user
        d.channel = None
        return d

    # ============================================================
    # COMMAND GROUP
    # ============================================================
    @commands.group(name="taskpacket", aliases=["tp"])
    @checks.is_owner()
    async def taskpacket(self, ctx):
        pass

    # ============================================================
    # LIST GROUPS
    # ============================================================
    @taskpacket.command(name="list")
    async def tp_list(self, ctx):
        groups = await self.config.groups()
        if not groups:
            return await ctx.send("No task groups created yet.")

        embed = discord.Embed(title="TaskPacket Groups", color=discord.Color.blue())
        for name, cmds in groups.items():
            text = (
                "\n".join(f"**{i+1}.** `{c}`" for i, c in enumerate(cmds)) or "*empty*"
            )
            embed.add_field(name=name, value=text, inline=False)
        await ctx.send(embed=embed)

    # ============================================================
    # CREATE GROUP
    # ============================================================
    @taskpacket.command(name="create")
    async def tp_create(self, ctx, group: str):
        groups = await self.config.groups()

        if group in groups:
            return await ctx.send("❌ Group already exists.")

        groups[group] = []
        await self.config.groups.set(groups)
        await ctx.send(f"✅ Created group **{group}**")

    # ============================================================
    # DELETE GROUP
    # ============================================================
    @taskpacket.command(name="delete")
    async def tp_delete(self, ctx, group: str):
        groups = await self.config.groups()

        if group not in groups:
            return await ctx.send("❌ Group not found.")

        del groups[group]
        await self.config.groups.set(groups)
        await ctx.send(f"🗑 Deleted group **{group}**")

    # ============================================================
    # ADD
    # ============================================================
    @taskpacket.command(name="add")
    async def tp_add(self, ctx, group: str, *, command_string: str):
        groups = await self.config.groups()

        if group not in groups:
            return await ctx.send("❌ Group not found.")

        groups[group].append(command_string)
        await self.config.groups.set(groups)
        await ctx.send(f"📌 Added to **{group}**:\n`{command_string}`")

    # ============================================================
    # REMOVE
    # ============================================================
    @taskpacket.command(name="remove")
    async def tp_remove(self, ctx, group: str, index: int):
        groups = await self.config.groups()

        if group not in groups:
            return await ctx.send("❌ Group not found.")

        cmds = groups[group]
        if not (1 <= index <= len(cmds)):
            return await ctx.send("❌ Invalid index.")

        removed = cmds.pop(index - 1)
        await self.config.groups.set(groups)
        await ctx.send(f"🧹 Removed `{removed}` from **{group}**")

    # ============================================================
    # MOVE
    # ============================================================
    @taskpacket.command(name="move")
    async def tp_move(self, ctx, group: str, old_index: int, new_index: int):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")

        cmds = groups[group]
        if not (1 <= old_index <= len(cmds)) or not (1 <= new_index <= len(cmds)):
            return await ctx.send("❌ Invalid indexes.")

        cmd = cmds.pop(old_index - 1)
        cmds.insert(new_index - 1, cmd)
        await self.config.groups.set(groups)
        await ctx.send(f"🔀 Moved command in **{group}**")

    # ============================================================
    # RUN GROUP ONCE
    # ============================================================
    @taskpacket.command(name="run")
    async def tp_run(self, ctx, group: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")
        if not groups[group]:
            return await ctx.send("⚠ Group is empty.")

        await ctx.send(f"▶ Running **{group}**…")

        for cmd in groups[group]:
            try:
                # use the real ctx so run_bot_command can use its state safely
                await self.run_bot_command(ctx, cmd, channel=ctx.channel)
            except Exception as e:
                await ctx.send(f"❌ Error executing `{cmd}`:\n`{e}`")

        await ctx.send(f"✅ Completed **{group}**")

    # ============================================================
    # REPEAT
    # ============================================================
    @taskpacket.command(name="repeat")
    async def tp_repeat(self, ctx, group: str, interval: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")

        try:
            seconds = parse_interval(interval)
        except ValueError as e:
            return await ctx.send(f"❌ {e}")

        # prepare storage entry (capture live state/prefix/author)
        state_repr = self._capture_state_and_prefix(ctx)
        author_id = ctx.author.id
        prefix = ctx.prefix

        task_id = str(int(time.time() * 1000))
        entry = {
            "group": group,
            "interval": seconds,
            "interval_raw": interval,
            "channel_id": ctx.channel.id,
            "next_run": time.time() + seconds,
            "state_repr": state_repr,
            "author_id": author_id,
            "prefix": prefix,
        }

        # store persistently
        await self.config.repeats.set_raw(task_id, value=entry)

        # spawn loop and track
        loop_task = asyncio.create_task(self._repeat_loop(task_id, entry))
        self.running_tasks[task_id] = loop_task

        await ctx.send(f"🔁 Scheduled **{group}** every **{interval}**.")

    # ============================================================
    # SCHEDULE LIST
    # ============================================================
    @taskpacket.command(name="schedule")
    async def tp_schedule(self, ctx):
        stored = await self.config.repeats()
        if not stored:
            return await ctx.send("📭 No scheduled repeat tasks.")

        now = time.time()
        embed = discord.Embed(
            title="⏰ Scheduled Repeat Tasks", color=discord.Color.green()
        )

        for idx, (task_id, data) in enumerate(stored.items()):
            remaining = max(0, int(data.get("next_run", 0) - now))
            readable = str(timedelta(seconds=remaining))
            embed.add_field(
                name=f"#{idx}",
                value=(
                    f"**Group:** `{data['group']}`\n"
                    f"**Interval:** `{data['interval_raw']}`\n"
                    f"**Channel:** <#{data['channel_id']}>\n"
                    f"**Next run:** `{readable}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ============================================================
    # STOP
    # ============================================================
    @taskpacket.command(name="stop")
    async def tp_stop(self, ctx, index: int):
        stored = await self.config.repeats()
        if not stored:
            return await ctx.send("❌ No active repeat tasks.")

        if index < 0 or index >= len(stored):
            return await ctx.send("❌ Invalid task index.")

        task_id = list(stored.keys())[index]

        # cancel running
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]

        # remove from config
        await self.config.repeats.clear_raw(task_id)

        await ctx.send(f"⏹ Stopped scheduled repeat at index **{index}**.")

    # ============================================================
    # GHOST CHECK (keeps your existing helper)
    # ============================================================
    @commands.is_owner()
    @taskpacket.command(name="checkghost")
    async def tp_checkghost(self, ctx):
        tasks = []
        for task in asyncio.all_tasks():
            if (
                "repeat_loop" in str(task)
                or "_repeat_loop" in str(task)
                or "run_bot_command" in str(task)
            ):
                tasks.append(str(task))

        if not tasks:
            await ctx.send("✅ No ghost repeat tasks exist.")
        else:
            await ctx.send("⚠️ Ghost tasks found:\n```\n" + "\n".join(tasks) + "\n```")

    # ============================================================
    # COG UNLOAD
    # ============================================================
    def cog_unload(self):
        for t in self.running_tasks.values():
            try:
                t.cancel()
            except:
                pass
        self.running_tasks.clear()


# ============================================================
# SETUP
# ============================================================
async def setup(bot: Red):
    await bot.add_cog(TaskPacket(bot))
