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

        # Wrap get_command so help lookups can't find disabled commands
        self._old_get_command = bot.get_command
        bot.get_command = self._intercept_get_command

    async def cog_unload(self):
        # Restore original methods
        self.bot.invoke = self._old_invoke
        self.bot.get_command = self._old_get_command

    async def _intercept_invoke(self, ctx: commands.Context):
        """Intercept and cancel globally disabled commands before they run."""
        if ctx.command and ctx.command.qualified_name.lower() in self.globally_disabled:
            return  # silently block
        await self._old_invoke(ctx)

    def _intercept_get_command(self, name: str):
        """Intercept command lookup so help can't even find disabled commands."""
        cmd = self._old_get_command(name)
        if cmd and cmd.qualified_name.lower() in self.globally_disabled:
            return None
        return cmd


async def setup(bot: Red):
    await bot.add_cog(SDisable(bot))
