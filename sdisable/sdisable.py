import discord
from redbot.core import commands
from redbot.core.bot import Red


class SDisable(commands.Cog):
    """Globally disable specific commands for everyone, including the owner."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.globally_disabled = {
            "about",
            "licenseinfo",
            "info",
            "contact",
            "version",
            "changelog",
            "licenses",
        }

        # Wrap invoke to hard-block execution
        self._old_invoke = bot.invoke
        bot.invoke = self._intercept_invoke

        # Wrap send_help_for to hide in help
        self._old_send_help = bot.send_help_for
        bot.send_help_for = self._intercept_help

    async def cog_unload(self):
        # Restore original methods
        self.bot.invoke = self._old_invoke
        self.bot.send_help_for = self._old_send_help

    async def _intercept_invoke(self, ctx: commands.Context):
        """Intercept and cancel globally disabled commands before they run."""
        if ctx.command and ctx.command.qualified_name.lower() in self.globally_disabled:
            return  # silently block
        await self._old_invoke(ctx)

    async def _intercept_help(self, *args, **kwargs):
        """Intercept help command output to hide disabled commands."""
        if len(args) > 1:
            target = args[1]
            if isinstance(target, commands.Command):
                if target.qualified_name.lower() in self.globally_disabled:
                    return  # hide entirely
            elif isinstance(target, commands.Cog):
                # Keep original get_commands to restore later if needed
                if not hasattr(target, "__original_get_commands__"):
                    target.__original_get_commands__ = target.get_commands
                target.get_commands = lambda *a, **k: [
                    cmd
                    for cmd in target.__original_get_commands__(*a, **k)
                    if cmd.qualified_name.lower() not in self.globally_disabled
                ]
        return await self._old_send_help(*args, **kwargs)


async def setup(bot: Red):
    await bot.add_cog(SDisable(bot))