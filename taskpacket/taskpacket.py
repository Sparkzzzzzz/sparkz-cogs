import asyncio
import discord
import re
import time
from datetime import timedelta

from redbot.core import commands, checks, Config
from redbot.core.bot import Red


# =====================================================================
# INTERVAL PARSER
# =====================================================================
def parse_interval(text: str) -> int:
    """
    Convert strings like '5h6m12s' into seconds.
    Supports: 10s, 5m, 2h, 1h30m, 3h15s, 4h2m9s, etc.
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

        # List of scheduled tasks
        # Each entry: {group, interval, interval_raw, task, next_run}
        self.repeat_tasks = []

    # =====================================================================
    # INTERNAL: SAFE COMMAND RUNNER
    # =====================================================================
    async def run_bot_command(self, ctx, command_string: str):
        """
        Safely execute another bot command as if the user typed it.
        Creates a REAL fake Message object with proper internal state.
        """

        state = ctx.message._state

        fake_message = discord.Message(
            state=state,
            channel=ctx.channel,
            data={
                "id": ctx.message.id,
                "type": 0,
                "content": ctx.prefix + command_string,
                "channel_id": ctx.channel.id,
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
            },
        )

        new_ctx = await self.bot.get_context(fake_message, cls=type(ctx))
        await self.bot.invoke(new_ctx)

    # =====================================================================
    # BASE COMMAND GROUP
    # =====================================================================
    @commands.group(name="taskpacket", aliases=["tp"])
    @checks.admin()
    async def taskpacket(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    # =====================================================================
    # LIST GROUPS
    # =====================================================================
    @taskpacket.command(name="list")
    async def tp_list(self, ctx):
        groups = await self.config.groups()
        if not groups:
            return await ctx.send("No task groups created yet.")

        embed = discord.Embed(
            title="TaskPacket Groups",
            color=discord.Color.blue(),
        )

        for name, cmds in groups.items():
            text = (
                "\n".join(f"**{i+1}.** `{c}`" for i, c in enumerate(cmds)) or "*empty*"
            )
            embed.add_field(name=name, value=text, inline=False)

        await ctx.send(embed=embed)

    # =====================================================================
    # CREATE GROUP
    # =====================================================================
    @taskpacket.command(name="create")
    async def tp_create(self, ctx, group: str):
        groups = await self.config.groups()

        if group in groups:
            return await ctx.send("❌ Group already exists.")

        groups[group] = []
        await self.config.groups.set(groups)
        await ctx.send(f"✅ Created group **{group}**")

    # =====================================================================
    # DELETE GROUP
    # =====================================================================
    @taskpacket.command(name="delete")
    async def tp_delete(self, ctx, group: str):
        groups = await self.config.groups()

        if group not in groups:
            return await ctx.send("❌ Group not found.")

        del groups[group]
        await self.config.groups.set(groups)
        await ctx.send(f"🗑 Deleted group **{group}**")

    # =====================================================================
    # ADD COMMAND
    # =====================================================================
    @taskpacket.command(name="add")
    async def tp_add(self, ctx, group: str, *, command_string: str):
        groups = await self.config.groups()

        if group not in groups:
            return await ctx.send("❌ Group not found.")

        groups[group].append(command_string)
        await self.config.groups.set(groups)
        await ctx.send(f"📌 Added to **{group}**:\n`{command_string}`")

    # =====================================================================
    # REMOVE COMMAND
    # =====================================================================
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

    # =====================================================================
    # MOVE COMMAND
    # =====================================================================
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

    # =====================================================================
    # RUN GROUP ONCE
    # =====================================================================
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
                await self.run_bot_command(ctx, cmd)
            except Exception as e:
                await ctx.send(f"❌ Error executing `{cmd}`:\n`{e}`")

        await ctx.send(f"✅ Completed **{group}**")

    # =====================================================================
    # REPEAT GROUP (MULTIPLE SCHEDULES)
    # =====================================================================
    @taskpacket.command(name="repeat")
    async def tp_repeat(self, ctx, group: str, interval: str):
        groups = await self.config.groups()

        if group not in groups:
            return await ctx.send("❌ Group not found.")

        try:
            seconds = parse_interval(interval)
        except ValueError as e:
            return await ctx.send(f"❌ {e}")

        await ctx.send(f"🔁 Scheduled **{group}** every **{interval}**.")

        async def repeat_loop():
            while True:
                cmds_snapshot = (await self.config.groups())[group].copy()

                for cmd in cmds_snapshot:
                    try:
                        await self.run_bot_command(ctx, cmd)
                    except Exception as e:
                        await ctx.send(f"❌ Error executing `{cmd}`:\n`{e}`")

                entry["next_run"] = time.time() + seconds
                await asyncio.sleep(seconds)

        entry = {
            "group": group,
            "interval": seconds,
            "interval_raw": interval,
            "task": None,
            "next_run": time.time() + seconds,
        }

        loop_task = self.bot.loop.create_task(repeat_loop())
        entry["task"] = loop_task

        self.repeat_tasks.append(entry)

    # =====================================================================
    # LIST SCHEDULED TASKS
    # =====================================================================
    @taskpacket.command(name="schedule")
    async def tp_schedule(self, ctx):
        if not self.repeat_tasks:
            return await ctx.send("📭 No scheduled repeat tasks.")

        embed = discord.Embed(
            title="⏰ Scheduled Repeat Tasks", color=discord.Color.green()
        )

        now = time.time()

        for idx, entry in enumerate(self.repeat_tasks):
            remaining = max(0, int(entry["next_run"] - now))
            readable = str(timedelta(seconds=remaining))

            embed.add_field(
                name=f"#{idx}",
                value=(
                    f"**Group:** `{entry['group']}`\n"
                    f"**Interval:** `{entry['interval_raw']}`\n"
                    f"**Next run:** `{readable}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # =====================================================================
    # STOP SPECIFIC TASK BY INDEX
    # =====================================================================
    @taskpacket.command(name="stop")
    async def tp_stop(self, ctx, index: int):
        if index < 0 or index >= len(self.repeat_tasks):
            return await ctx.send("❌ Invalid task index.")

        entry = self.repeat_tasks.pop(index)
        entry["task"].cancel()

        await ctx.send(
            f"⏹ Stopped scheduled repeat for **{entry['group']}** (index {index})."
        )

    # =====================================================================
    # STOP ALL TASKS ON COG UNLOAD (HOT RELOAD SAFETY)
    # =====================================================================
    def cog_unload(self):
        for entry in self.repeat_tasks:
            try:
                entry["task"].cancel()
            except:
                pass
        self.repeat_tasks.clear()


# =====================================================================
# SETUP
# =====================================================================
async def setup(bot: Red):
    await bot.add_cog(TaskPacket(bot))
