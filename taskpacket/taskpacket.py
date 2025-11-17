import discord
from redbot.core import commands, Config
import asyncio
import datetime
import re


def parse_time(time_str: str) -> int:
    """
    Convert strings like '5h', '10m', '2h30m10s' into seconds.
    """
    pattern = r"((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?"
    match = re.fullmatch(pattern, time_str)
    if not match:
        raise ValueError("Invalid time format. Use formats like 5h, 5h30m, 10m20s, 30s")

    hours = int(match.group("hours")) if match.group("hours") else 0
    minutes = int(match.group("minutes")) if match.group("minutes") else 0
    seconds = int(match.group("seconds")) if match.group("seconds") else 0

    total_seconds = hours * 3600 + minutes * 60 + seconds
    if total_seconds <= 0:
        raise ValueError("Time must be greater than 0 seconds.")

    return total_seconds


class TaskPacket(commands.Cog):
    """
    TaskPacket Scheduler
    Option B — tasks stop on reload (no persistence)
    Executes each line as a bot command.
    """

    def __init__(self, bot):
        self.bot = bot
        self.active_tasks = {}  # {id: asyncio.Task}
        self.task_data = {}  # {id: {"author":, "channel":, "interval":, "lines":}}

    # -----------------------------
    # Utility
    # -----------------------------
    async def run_packet(self, ctx, lines):
        """
        Execute each line as if user typed it.
        """
        for line in lines:
            if not line.strip():
                continue

            fake_msg = ctx.message
            fake_msg.content = ctx.prefix + line

            new_ctx = await self.bot.get_context(fake_msg)
            if new_ctx.valid:
                await self.bot.invoke(new_ctx)
            await asyncio.sleep(0.5)

    # -----------------------------
    # Commands
    # -----------------------------

    @commands.command(name="tp")
    async def taskpacket(self, ctx, *, block: str):
        """
        Run a one-time task packet immediately.
        """
        lines = block.strip().split("\n")
        await ctx.send("▶ Running TaskPacket…")
        await self.run_packet(ctx, lines)
        await ctx.send("✅ TaskPacket complete.")

    @commands.command(name="tp_repeat")
    async def tp_repeat(self, ctx, interval: str, *, block: str):
        """
        Create a repeating task that runs every X (h/m/s).
        """
        try:
            seconds = parse_time(interval)
        except ValueError as e:
            return await ctx.send(f"❌ {e}")

        task_id = len(self.task_data) + 1
        lines = block.strip().split("\n")

        # Save task details
        self.task_data[task_id] = {
            "author": ctx.author.id,
            "channel": ctx.channel.id,
            "interval": seconds,
            "lines": lines,
        }

        # Create background task
        self.active_tasks[task_id] = self.bot.loop.create_task(
            self._run_repeater(task_id, ctx)
        )

        await ctx.send(
            f"⏳ Scheduled repeat task **#{task_id}** every `{interval}`.\n"
            f"Use `.tp_stop {task_id}` to stop it."
        )

    async def _run_repeater(self, task_id, ctx):
        """
        Main repeater loop.
        """
        data = self.task_data[task_id]
        channel = self.bot.get_channel(data["channel"])

        while True:
            try:
                await self.run_packet(ctx, data["lines"])
            except Exception:
                pass
            await asyncio.sleep(data["interval"])

    @commands.command(name="tp_schedule")
    async def tp_schedule(self, ctx):
        """
        Display active scheduled repeaters.
        """
        if not self.task_data:
            return await ctx.send("📮 No scheduled repeat tasks.")

        embed = discord.Embed(
            title="📌 Active Repeat Tasks",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow(),
        )

        for task_id, data in self.task_data.items():
            interval_str = str(datetime.timedelta(seconds=data["interval"]))
            embed.add_field(
                name=f"Task #{task_id}",
                value=f"⏱ Interval: `{interval_str}`\n"
                f"📌 Lines: `{len(data['lines'])}` commands",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.command(name="tp_stop")
    async def tp_stop(self, ctx, task_id: int):
        """
        Stop a running repeat task by ID.
        """
        if task_id not in self.active_tasks:
            return await ctx.send("❌ Invalid task ID.")

        # Cancel the task
        self.active_tasks[task_id].cancel()

        # Remove from trackers
        del self.active_tasks[task_id]
        del self.task_data[task_id]

        await ctx.send(f"🛑 Stopped task #{task_id}.")


async def setup(bot):
    await bot.add_cog(TaskPacket(bot))
