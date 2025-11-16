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

        # In-memory repeating loops (stop when cog reloads or bot restarts)
        self.repeat_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------
    # INTERNAL — Execute a command as user
    # ------------------------------------
    async def run_bot_command(self, ctx, command_string: str):
        """Safely execute another bot command as if user typed it."""
        msg = ctx.message
        fake = msg.copy()
        fake.content = ctx.prefix + command_string

        new_ctx = await self.bot.get_context(fake, cls=type(ctx))
        await self.bot.invoke(new_ctx)

    # ------------------------------------
    # ON UNLOAD — stop all tasks
    # ------------------------------------
    def cog_unload(self):
        """Called automatically when cog reloads or bot shuts down."""
        for task in self.repeat_tasks.values():
            task.cancel()
        self.repeat_tasks.clear()

    # ------------------------------------
    # Command Group
    # ------------------------------------
    @commands.group(name="taskpacket", aliases=["tp"])
    @checks.admin()
    async def taskpacket(self, ctx):
        """TaskPacket: manage groups of commands."""
        pass

    # ------------------------------------
    # LIST GROUPS
    # ------------------------------------
    @taskpacket.command(name="list")
    async def tp_list(self, ctx):
        groups = await self.config.groups()

        if not groups:
            return await ctx.send("No task groups created yet.")

        embed = discord.Embed(
            title="TaskPacket Groups",
            description="Stored command groups:",
            color=discord.Color.blue(),
        )

        for name, cmds in groups.items():
            text = (
                "\n".join(f"**{i+1}.** `{c}`" for i, c in enumerate(cmds)) or "*empty*"
            )
            embed.add_field(name=name, value=text, inline=False)

        await ctx.send(embed=embed)

    # ------------------------------------
    # CREATE GROUP
    # ------------------------------------
    @taskpacket.command(name="create")
    async def tp_create(self, ctx, group: str):
        groups = await self.config.groups()
        if group in groups:
            return await ctx.send("❌ Group already exists.")

        groups[group] = []
        await self.config.groups.set(groups)
        await ctx.send(f"✅ Created group **{group}**")

    # ------------------------------------
    # DELETE GROUP
    # ------------------------------------
    @taskpacket.command(name="delete")
    async def tp_delete(self, ctx, group: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")

        del groups[group]
        await self.config.groups.set(groups)
        await ctx.send(f"🗑 Deleted group **{group}**")

    # ------------------------------------
    # ADD COMMAND
    # ------------------------------------
    @taskpacket.command(name="add")
    async def tp_add(self, ctx, group: str, *, command_string: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")

        groups[group].append(command_string)
        await self.config.groups.set(groups)
        await ctx.send(f"📌 Added `{command_string}` to **{group}**")

    # ------------------------------------
    # REMOVE COMMAND
    # ------------------------------------
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

    # ------------------------------------
    # MOVE COMMAND
    # ------------------------------------
    @taskpacket.command(name="move")
    async def tp_move(self, ctx, group: str, old_index: int, new_index: int):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")

        cmds = groups[group]
        if not (1 <= old_index <= len(cmds)) or not (1 <= new_index <= len(cmds)):
            return await ctx.send("❌ Invalid index.")

        cmd = cmds.pop(old_index - 1)
        cmds.insert(new_index - 1, cmd)

        await self.config.groups.set(groups)
        await ctx.send(f"🔀 Moved command to position {new_index} in **{group}**")

    # ------------------------------------
    # RUN GROUP ONCE
    # ------------------------------------
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

    # ------------------------------------
    # REPEAT GROUP
    # ------------------------------------
    @taskpacket.command(name="repeat")
    async def tp_repeat(self, ctx, group: str, interval: int):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")

        if interval < 1:
            return await ctx.send("❌ Interval must be ≥ 1 second.")

        # Stop any old task
        if group in self.repeat_tasks:
            self.repeat_tasks[group].cancel()
            del self.repeat_tasks[group]

        await ctx.send(f"🔁 Repeating **{group}** every **{interval} seconds**.")

        async def loop():
            try:
                while True:
                    cmds_snapshot = list(
                        (await self.config.groups())[group]
                    )  # fresh snapshot every loop
                    for cmd in cmds_snapshot:
                        try:
                            await self.run_bot_command(ctx, cmd)
                        except Exception as e:
                            await ctx.send(f"❌ Error executing `{cmd}`:\n`{e}`")
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return

        task = self.bot.loop.create_task(loop())
        self.repeat_tasks[group] = task

    # ------------------------------------
    # STOP REPEATING
    # ------------------------------------
    @taskpacket.command(name="stoprepeat")
    async def tp_stoprepeat(self, ctx, group: str):
        if group not in self.repeat_tasks:
            return await ctx.send(f"⚠ No repeating task running for **{group}**.")

        self.repeat_tasks[group].cancel()
        del self.repeat_tasks[group]
        await ctx.send(f"⏹ Stopped repeating **{group}**.")


async def setup(bot: Red):
    await bot.add_cog(TaskPacket(bot))
