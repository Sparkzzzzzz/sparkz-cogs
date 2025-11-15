import asyncio
import discord
from redbot.core import commands, checks, Config
from redbot.core.bot import Red


class TaskPacket(commands.Cog):
    """Create groups of commands that execute in sequence, with optional repeated scheduling."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=762829303, force_registration=True
        )
        self.config.register_global(groups={})
        self.repeat_tasks = {}  # in-memory repeating tasks, stop on unload/reload

    # -------------------------------
    # INTERNAL: Run a command
    # -------------------------------
    async def run_bot_command(self, ctx, command_string: str):
        """Execute a command string as if the user typed it."""
        new_ctx = await self.bot.get_context(ctx.message, cls=type(ctx))
        new_ctx.message.content = ctx.prefix + command_string
        await self.bot.invoke(new_ctx)

    # -------------------------------
    # COMMAND GROUP
    # -------------------------------
    @commands.group(name="taskpacket", aliases=["tp"])
    @checks.admin()
    async def taskpacket(self, ctx):
        """TaskPacket: manage groups of commands."""
        if ctx.invoked_subcommand is None:
            return

    # -------------------------------
    # LIST GROUPS
    # -------------------------------
    @taskpacket.command(name="list")
    async def tp_list(self, ctx):
        groups = await self.config.groups()
        if not groups:
            return await ctx.send("No task groups created yet.")

        embed = discord.Embed(
            title="TaskPacket Groups",
            description="All groups and their commands:",
            color=discord.Color.blue(),
        )
        for name, cmds in groups.items():
            formatted = (
                "\n".join(f"**{i+1}.** `{c}`" for i, c in enumerate(cmds)) or "*empty*"
            )
            embed.add_field(name=name, value=formatted, inline=False)
        await ctx.send(embed=embed)

    # -------------------------------
    # CREATE GROUP
    # -------------------------------
    @taskpacket.command(name="create")
    async def tp_create(self, ctx, group: str):
        groups = await self.config.groups()
        if group in groups:
            return await ctx.send("❌ Group already exists.")
        groups[group] = []
        await self.config.groups.set(groups)
        await ctx.send(f"✅ Created group **{group}**")

    # -------------------------------
    # DELETE GROUP
    # -------------------------------
    @taskpacket.command(name="delete")
    async def tp_delete(self, ctx, group: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")
        del groups[group]
        await self.config.groups.set(groups)
        await ctx.send(f"🗑 Deleted group **{group}**")

    # -------------------------------
    # ADD COMMAND
    # -------------------------------
    @taskpacket.command(name="add")
    async def tp_add(self, ctx, group: str, *, command_string: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")
        groups[group].append(command_string)
        await self.config.groups.set(groups)
        await ctx.send(f"📌 Added to **{group}**:\n`{command_string}`")

    # -------------------------------
    # REMOVE COMMAND
    # -------------------------------
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

    # -------------------------------
    # MOVE COMMAND
    # -------------------------------
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
        await ctx.send(f"🔀 Moved command to position {new_index} in **{group}**")

    # -------------------------------
    # RUN TASK GROUP
    # -------------------------------
    @taskpacket.command(name="run", aliases=["exec"])
    async def tp_run(self, ctx, group: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")
        cmds = groups[group]
        if not cmds:
            return await ctx.send("⚠ Group is empty.")

        await ctx.send(f"▶ Running **{group}**…")
        for cmd in cmds:
            try:
                await self.run_bot_command(ctx, cmd)
            except Exception as e:
                await ctx.send(f"❌ Error executing `{cmd}`:\n`{e}`")
        await ctx.send(f"✅ Completed **{group}**")

    # -------------------------------
    # REPEAT TASK GROUP (IN-MEMORY ONLY)
    # -------------------------------
    @taskpacket.command(name="repeat")
    async def tp_repeat(self, ctx, group: str, interval: int):
        """Run a task group repeatedly every <interval> seconds (in-memory only)."""
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")
        if interval < 1:
            return await ctx.send("❌ Interval must be at least 1 second.")

        # Stop previous loop if exists
        if group in self.repeat_tasks:
            self.repeat_tasks[group].cancel()

        await ctx.send(
            f"🔁 Started repeating **{group}** every **{interval} seconds**."
        )

        async def repeat_loop():
            while True:
                # make a fresh snapshot for each iteration to preserve order
                cmds_snapshot = groups[group].copy()
                for cmd in cmds_snapshot:
                    try:
                        new_ctx = await self.bot.get_context(ctx.message, cls=type(ctx))
                        new_ctx.message.content = ctx.prefix + cmd
                        await self.bot.invoke(new_ctx)
                    except Exception as e:
                        await ctx.send(f"❌ Error executing `{cmd}`:\n`{e}`")
                await asyncio.sleep(interval)

        self.repeat_tasks[group] = self.bot.loop.create_task(repeat_loop())

    # -------------------------------
    # STOP REPEATING TASK
    # -------------------------------
    @taskpacket.command(name="stoprepeat")
    async def tp_stoprepeat(self, ctx, group: str):
        """Stop a repeating task group."""
        if group not in self.repeat_tasks:
            return await ctx.send(f"⚠ No repeating task found for **{group}**.")

        self.repeat_tasks[group].cancel()
        del self.repeat_tasks[group]
        await ctx.send(f"⏹ Stopped repeating **{group}**.")


async def setup(bot: Red):
    await bot.add_cog(TaskPacket(bot))
