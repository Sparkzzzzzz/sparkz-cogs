import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red


class TaskPacket(commands.Cog):
    """Create groups of commands that execute in sequence."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=762829303, force_registration=True
        )
        # groups: { "groupname": ["cmd arg1", "cmd arg2"] }
        self.config.register_global(groups={})

    # ------------------------------------------------------------
    # INTERNAL: simulate a command
    # ------------------------------------------------------------
    async def run_bot_command(self, ctx, command_string: str):
        """Execute a command string as if the user typed it."""
        parts = command_string.split()
        if not parts:
            return
        cmd_name, *args = parts

        cmd = self.bot.get_command(cmd_name)
        if not cmd:
            await ctx.send(f"❌ Command `{cmd_name}` not found.")
            return

        # Make a new context, preserve author & channel
        new_ctx = await self.bot.get_context(ctx.message)
        new_ctx.message.content = ctx.prefix + command_string

        try:
            await cmd.invoke(new_ctx)
        except Exception as e:
            await ctx.send(f"❌ Error executing `{command_string}`:\n`{e}`")

    # ------------------------------------------------------------
    # COMMAND GROUP
    # ------------------------------------------------------------
    @commands.group(name="taskpacket", aliases=["tp"])
    @checks.admin()
    async def taskpacket(self, ctx):
        """TaskPacket: manage groups of commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("⚠ Please specify a subcommand. Use `.tp help` for options.")

    # ------------------------------------------------------------
    # LIST GROUPS
    # ------------------------------------------------------------
    @taskpacket.command(name="list")
    async def tp_list(self, ctx):
        """List all task groups and their commands."""
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

    # ------------------------------------------------------------
    # CREATE GROUP
    # ------------------------------------------------------------
    @taskpacket.command(name="create")
    async def tp_create(self, ctx, group: str):
        groups = await self.config.groups()
        if group in groups:
            return await ctx.send("❌ Group already exists.")
        groups[group] = []
        await self.config.groups.set(groups)
        await ctx.send(f"✅ Created group **{group}**")

    # ------------------------------------------------------------
    # DELETE GROUP
    # ------------------------------------------------------------
    @taskpacket.command(name="delete")
    async def tp_delete(self, ctx, group: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")
        del groups[group]
        await self.config.groups.set(groups)
        await ctx.send(f"🗑 Deleted group **{group}**")

    # ------------------------------------------------------------
    # ADD COMMAND
    # ------------------------------------------------------------
    @taskpacket.command(name="add")
    async def tp_add(self, ctx, group: str, *, command_string: str):
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("❌ Group not found.")
        groups[group].append(command_string)
        await self.config.groups.set(groups)
        await ctx.send(f"📌 Added to **{group}**:\n`{command_string}`")

    # ------------------------------------------------------------
    # REMOVE COMMAND
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # MOVE / REORDER
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # RUN TASK PACKET
    # ------------------------------------------------------------
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
            await self.run_bot_command(ctx, cmd)
        await ctx.send(f"✅ Completed **{group}**")


async def setup(bot: Red):
    await bot.add_cog(TaskPacket(bot))
