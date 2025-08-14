import discord
from redbot.core import commands
from redbot.core.bot import Red


class SDisable(commands.Cog):
    """Globally disable specific commands for everyone, including the owner."""

    def __init__(self, bot: Red):
        self.bot = bot
        # Exact command names to block (lowercase)
        self.globally_disabled = {
            "about",
            "licenseinfo",
            "info",
            "contact",
            "uptime",
            "ping",
            "version",
            "changelog",
            "licenses",
        }
        self._old_invoke = bot.invoke
        bot.invoke = self._intercept_invoke

    async def cog_unload(self):
        # Restore original invoke method
        self.bot.invoke = self._old_invoke

    async def _intercept_invoke(self, ctx: commands.Context):
        """Intercept and cancel globally disabled commands before they run."""
        if ctx.command and ctx.command.qualified_name.lower() in self.globally_disabled:
            return  # silently do nothing
        await self._old_invoke(ctx)


async def setup(bot: Red):
    await bot.add_cog(SDisable(bot))
