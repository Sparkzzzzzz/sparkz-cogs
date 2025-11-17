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

        # Keep groups and repeats in config (primitives only)
        self.config.register_global(groups={})
        self.config.register_global(repeats={})
        # Format in config.repeats:
        # key = task_id (string)
        # value = { group, interval, interval_raw, channel_id, next_run, author_id, prefix }

        self.running_tasks = {}  # task_id -> asyncio Task

        # restore tasks on startup (in-memory only tasks are re-created from config)
        asyncio.create_task(self._startup_load())

    # ============================================================
    # STARTUP: RESTORE TASKS
    # ============================================================
    async def _startup_load(self):
        await self.bot.wait_until_ready()
        stored = await self.config.repeats()
        for task_id, data in stored.items():
            try:
                # basic validation
                group = data.get("group")
                interval = data.get("interval")
                channel_id = data.get("channel_id")
                if not group or not interval or not channel_id:
                    continue
                # try to resolve channel; if missing, still spawn loop (it will try fetch)
                loop_task = asyncio.create_task(self._repeat_loop(task_id, data))
                self.running_tasks[task_id] = loop_task
            except Exception:
                # don't allow startup to fail for one entry
                continue

    # ============================================================
    # RUN BOT COMMAND - scheduled execution (no non-serializable saved)
    # ============================================================
    async def run_bot_command_scheduled(
        self,
        command_string: str,
        channel: discord.abc.Messageable,
        author_id: int,
        prefix: str,
    ):
        """
        Execute a bot command string in the given channel using a rebuilt Message
        with the bot's live connection state (self.bot._connection). This function
        is used by scheduled tasks (no ctx available).
        """
        # Resolve author object (best-effort)
        author = None
        try:
            author = self.bot.get_user(author_id) or await self.bot.fetch_user(
                author_id
            )
        except Exception:
            author = None

        # Build author data for message payload (not stored in config)
        author_data = {
            "id": author.id if author else author_id,
            "username": getattr(author, "name", "Unknown") if author else "Unknown",
            "avatar": (
                getattr(author, "avatar", None).key
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

        # Use the bot's live connection state (do NOT store this)
        state = getattr(self.bot, "_connection", None)

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
            new_ctx = await self.bot.get_context(fake_message, cls=commands.Context)
            await self.bot.invoke(new_ctx)
        except Exception as exc:
            # fallback minimal message-like object for get_context if Message fails
            try:

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
            except Exception as exc2:
                # If both methods fail, raise so the caller can log
                raise exc2

    # ============================================================
    # RUN BOT COMMAND - direct ctx path (used by tp_run)
    # ============================================================
    async def run_bot_command_direct(self, ctx, command_string: str):
        """
        Execute command using a real ctx (when running .tp run).
        This keeps identical behavior to a user typing the command.
        """
        # mutate message content temporarily and restore after
        orig = ctx.message.content
        try:
            ctx.message.content = (ctx.prefix or "") + command_string
            new_ctx = await self.bot.get_context(ctx.message, cls=type(ctx))
            await self.bot.invoke(new_ctx)
        finally:
            ctx.message.content = orig

    # ============================================================
    # BACKGROUND LOOP FOR EACH TASK
    # ============================================================
    async def _repeat_loop(self, task_id: str, data: dict):
        """
        Loop running each scheduled task. Data is the primitive-only dict from config.
        """
        group = data["group"]
        interval = data["interval"]
        channel_id = data["channel_id"]
        author_id = data.get("author_id")
        prefix = data.get("prefix", "")

        while True:
            try:
                groups = await self.config.groups()
                if group not in groups:
                    # group removed → cleanup config and stop
                    try:
                        await self.config.repeats.clear_raw(task_id)
                    except Exception:
                        pass
                    break

                cmds = groups[group].copy()

                # resolve channel fresh each iteration
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    # try fetch
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception:
                        # can't resolve channel, skip this cycle but update next_run
                        data["next_run"] = time.time() + interval
                        await self.config.repeats.set_raw(task_id, value=data)
                        await asyncio.sleep(interval)
                        continue

                # run each command string as a bot command using scheduled runner
                for cmd in cmds:
                    try:
                        await self.run_bot_command_scheduled(
                            cmd, channel, author_id, prefix
                        )
                    except Exception as exc:
                        # try report into the channel
                        try:
                            await channel.send(f"❌ Error executing `{cmd}`:\n`{exc}`")
                        except Exception:
                            pass

                # update next_run and persist minimal primitives
                data["next_run"] = time.time() + interval
                await self.config.repeats.set_raw(task_id, value=data)

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return
            except Exception:
                # resilience: wait a bit and continue
                try:
                    await asyncio.sleep(max(1, interval))
                except asyncio.CancelledError:
                    return

    # ============================================================
    # COMMAND GROUP
    # ============================================================
    @commands.group(name="taskpacket", aliases=["tp"])
    @checks.is_owner()
    async def taskpacket(self, ctx):
        if ctx.invoked_subcommand is None:
            return

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
    @taskpacket.command(name="run", aliases=["exec"])
    async def tp_run(self, ctx, group: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")
        if not groups[group]:
            return await ctx.send("⚠ Group is empty.")

        await ctx.send(f"▶ Running **{group}**…")

        for cmd in groups[group]:
            try:
                # use real ctx for direct run
                await self.run_bot_command_direct(ctx, cmd)
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

        # prepare minimal primitive-only entry
        task_id = str(int(time.time() * 1000))
        entry = {
            "group": group,
            "interval": seconds,
            "interval_raw": interval,
            "channel_id": ctx.channel.id,
            "next_run": time.time() + seconds,
            "author_id": ctx.author.id,
            "prefix": ctx.prefix or "",
        }

        # persist minimal primitives only
        await self.config.repeats.set_raw(task_id, value=entry)

        # spawn loop and track in-memory
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
        # improved: only flag _repeat_loop tasks that are NOT tracked in self.running_tasks
        stored = await self.config.repeats()
        tracked_tasks = set(self.running_tasks.values())
        ghosts = []

        for task in asyncio.all_tasks():
            try:
                coro = task.get_coro()
                # identify repeat loop coroutines by name or qualname
                coro_name = getattr(coro, "__name__", str(coro))
                coro_qname = getattr(coro, "__qualname__", None)
                if "_repeat_loop" in coro_name or (
                    coro_qname and "_repeat_loop" in coro_qname
                ):
                    # if this task object is not one of our tracked running tasks, it's a ghost
                    if task not in tracked_tasks:
                        ghosts.append(str(task))
            except Exception:
                # if something odd happens, include the representation to inspect
                if "_repeat_loop" in str(task):
                    ghosts.append(str(task))

        if not ghosts:
            await ctx.send("✅ No ghost repeat tasks exist.")
        else:
            await ctx.send("⚠️ Ghost tasks found:\n```\n" + "\n".join(ghosts) + "\n```")

    # ============================================================
    # PURGE GHOSTS - cancel any dangling repeat loops not tracked
    # ============================================================
    @commands.is_owner()
    @taskpacket.command(name="purgeghosts")
    async def tp_purgeghosts(self, ctx):
        stored = await self.config.repeats()
        tracked_tasks = set(self.running_tasks.values())
        killed = 0
        killed_info = []

        for task in list(asyncio.all_tasks()):
            try:
                coro = task.get_coro()
                coro_name = getattr(coro, "__name__", str(coro))
                coro_qname = getattr(coro, "__qualname__", None)
                if (
                    "_repeat_loop" in coro_name
                    or (coro_qname and "_repeat_loop" in coro_qname)
                    or "_repeat_loop" in str(coro)
                ):
                    if task not in tracked_tasks:
                        try:
                            task.cancel()
                            killed += 1
                            killed_info.append(str(task))
                        except Exception:
                            pass
            except Exception:
                if "_repeat_loop" in str(task):
                    try:
                        task.cancel()
                        killed += 1
                        killed_info.append(str(task))
                    except Exception:
                        pass

        if killed == 0:
            await ctx.send("✅ No ghost repeat tasks found to purge.")
        else:
            # report summary (don't spam with huge dumps)
            summary = "\n".join(killed_info[:10])
            if len(killed_info) > 10:
                summary += f"\n...and {len(killed_info)-10} more"
            await ctx.send(f"☠️ Purged {killed} ghost task(s):\n```\n{summary}\n```")

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
