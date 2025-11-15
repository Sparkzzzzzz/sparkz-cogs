import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red


class taskpacket(commands.Cog):
    """Execute a sequence of commands as a grouped task."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=762829303, force_registration=True
        )

        # groups = { "groupname": ["cmd1 arg1", "cmd2", "cmd3 args"] }
        self.config.register_global(groups={})

    # Utility --------------------------------------------------------------

    async def run_bot_command(self, ctx, full_command: str):
        """Runs a bot command string as if user typed it."""
        msg = ctx.message
        fake_message = msg.copy()
        fake_message.content = ctx.prefix + full_command
        new_ctx = await self.bot.get_context(fake_message, cls=type(ctx))
        await self.bot.invoke(new_ctx)

    # ----------------------------------------------------------------------
    # GROUP COMMANDS
    # ----------------------------------------------------------------------

    @commands.group(aliases=["tp"], invoke_without_command=True)
    @checks.admin()
    async def taskpacket(self, ctx):
        """Base command for taskpacket."""
        groups = await self.config.groups()
        if not groups:
            return await ctx.send("No task groups created yet.")
        embed = discord.Embed(title="taskpacket Groups", color=discord.Color.blue())
        for name, cmds in groups.items():
            embed.add_field(
                name=name,
                value="\n".join(f"{i+1}. {c}" for i, c in enumerate(cmds)) or "*empty*",
                inline=False,
            )
        await ctx.send(embed=embed)

    # ----------------------------------------------------------------------
    # CREATE GROUP
    # ----------------------------------------------------------------------

    @taskpacket.command(name="create")
    @checks.admin()
    async def tp_create(self, ctx, group: str):
        """Create a new task group."""
        groups = await self.config.groups()
        if group in groups:
            return await ctx.send("Group already exists.")

        groups[group] = []
        await self.config.groups.set(groups)
        await ctx.send(f"Created task group **{group}**.")

    # ----------------------------------------------------------------------
    # DELETE GROUP
    # ----------------------------------------------------------------------

    @taskpacket.command(name="delete")
    @checks.admin()
    async def tp_delete(self, ctx, group: str):
        """Delete a task group."""
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("Group not found.")

        del groups[group]
        await self.config.groups.set(groups)
        await ctx.send(f"Deleted group **{group}**.")

    # ----------------------------------------------------------------------
    # ADD COMMAND TO GROUP
    # ----------------------------------------------------------------------

    @taskpacket.command(name="add")
    @checks.admin()
    async def tp_add(self, ctx, group: str, *, command_string: str):
        """Add a command to a group's queue."""
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("Group not found.")

        groups[group].append(command_string)
        await self.config.groups.set(groups)
        await ctx.send(f"Added command to **{group}**:\n`{command_string}`")

    # ----------------------------------------------------------------------
    # REMOVE COMMAND BY INDEX
    # ----------------------------------------------------------------------

    @taskpacket.command(name="remove")
    @checks.admin()
    async def tp_remove(self, ctx, group: str, index: int):
        """Remove a command from a group by its index (1-based)."""
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("Group not found.")

        if not (1 <= index <= len(groups[group])):
            return await ctx.send("Invalid index.")

        removed = groups[group].pop(index - 1)
        await self.config.groups.set(groups)
        await ctx.send(f"Removed:\n`{removed}`\nfrom group **{group}**.")

    # ----------------------------------------------------------------------
    # REORDER COMMANDS
    # ----------------------------------------------------------------------

    @taskpacket.command(name="move")
    @checks.admin()
    async def tp_move(self, ctx, group: str, old_index: int, new_index: int):
        """
        Move a command from old_index to new_index.
        Indexes are 1-based.
        """
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("Group not found.")

        cmds = groups[group]
        if not (1 <= old_index <= len(cmds)) or not (1 <= new_index <= len(cmds)):
            return await ctx.send("Invalid index.")

        item = cmds.pop(old_index - 1)
        cmds.insert(new_index - 1, item)

        groups[group] = cmds
        await self.config.groups.set(groups)
        await ctx.send(f"Moved command to position {new_index} in **{group}**.")

    # ----------------------------------------------------------------------
    # EXECUTE GROUP
    # ----------------------------------------------------------------------

    @taskpacket.command(name="run", aliases=["exec"])
    @checks.admin()
    async def tp_run(self, ctx, group: str):
        """Execute all commands in a group in order."""
        groups = await self.config.groups()
        if group not in groups:
            return await ctx.send("Group not found.")

        cmds = groups[group]
        if not cmds:
            return await ctx.send("Group is empty.")

        await ctx.send(f"Running group **{group}**…")

        for cmd in cmds:
            try:
                await self.run_bot_command(ctx, cmd)
            except Exception as e:
                await ctx.send(f"Error executing `{cmd}`:\n`{e}`")

        await ctx.send(f"Completed execution of **{group}**.")

    # ----------------------------------------------------------------------


async def setup(bot: Red):
    await bot.add_cog(taskpacket(bot))
