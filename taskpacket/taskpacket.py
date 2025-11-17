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

        self.config.register_global(groups={})
        self.config.register_global(repeats={})
        # Format in config.repeats:
        # key = task_id
        # value = { group, interval, interval_raw, channel_id, next_run }

        self.running_tasks = {}  # task_id -> asyncio task

        asyncio.create_task(self._startup_load())

    # ============================================================
    # STARTUP: RESTORE TASKS
    # ============================================================
    async def _startup_load(self):
        await self.bot.wait_until_ready()
        stored = await self.config.repeats()

        for task_id, data in stored.items():
            group = data.get("group")
            interval = data.get("interval")
            channel_id = data.get("channel_id")

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue

            loop_task = asyncio.create_task(self._repeat_loop(task_id, data))
            self.running_tasks[task_id] = loop_task

    # ============================================================
    # SAFE COMMAND RUNNER
    # ============================================================
    async def run_bot_command(
        self, ctx, command_string: str, channel: discord.TextChannel
    ):
        """
        Safely execute another bot command as if typed by user.
        Builds a real fake Discord message.
        """

        state = ctx.message._state

        fake_data = {
            "id": ctx.message.id,
            "type": 0,
            "content": ctx.prefix + command_string,
            "channel_id": channel.id,
            "author": {
                "id": ctx.author.id,
                "username": ctx.author.name,
                "avatar": ctx.author.avatar.key if ctx.author.avatar else None,
                "discriminator": ctx.author.discriminator,
                "public_flags": ctx.author.public_flags.value,
            },
            "attachments": [],
            "embeds": [],
            "mentions": [],
            "mention_roles": [],
            "pinned": False,
            "tts": False,
            "timestamp": ctx.message.created_at.isoformat(),
        }

        fake_message = discord.Message(state=state, channel=channel, data=fake_data)
        new_ctx = await self.bot.get_context(fake_message, cls=type(ctx))
        await self.bot.invoke(new_ctx)

    # ============================================================
    # BACKGROUND LOOP FOR EACH TASK
    # ============================================================
    async def _repeat_loop(self, task_id: str, data: dict):
        group = data["group"]
        interval = data["interval"]
        channel = self.bot.get_channel(data["channel_id"])

        while True:
            groups = await self.config.groups()
            if group not in groups:
                break

            cmds = groups[group].copy()

            dummy_ctx = None
            # Pick any context trigger (first available command invoker)
            # but fake internally anyway.
            for cmd in self.bot.commands:
                dummy_ctx = cmd
                break

            if channel:
                for cmd in cmds:
                    try:
                        # Dummy context needed only for author/state prefix
                        await self.run_bot_command(
                            ctx=self._fake_ctx(),
                            command_string=cmd,
                            channel=channel,
                        )
                    except Exception:
                        pass

            # schedule next run
            data["next_run"] = time.time() + interval
            await self.config.repeats.set_raw(task_id, value=data)

            await asyncio.sleep(interval)

    def _fake_ctx(self):
        """Construct a minimal fake context-like object for run_bot_command."""

        class Dummy:
            pass

        d = Dummy()
        d.message = type(
            "FakeMsg",
            (),
            {"_state": self.bot._connection, "created_at": discord.utils.utcnow()},
        )
        d.prefix = "."
        d.author = self.bot.user
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
                await self.run_bot_command(ctx, cmd, ctx.channel)
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

        task_id = str(int(time.time() * 1000))
        entry = {
            "group": group,
            "interval": seconds,
            "interval_raw": interval,
            "channel_id": ctx.channel.id,
            "next_run": time.time() + seconds,
        }

        await self.config.repeats.set_raw(task_id, value=entry)

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
            remaining = max(0, int(data["next_run"] - now))
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
        
    @commands.is_owner()
    @commands.command()
    async def tp_checkghost(self, ctx):
        tasks = []
        for task in asyncio.all_tasks():
            if "repeat_runner" in str(task) or "run_bot_command" in str(task):
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
