import discord
from redbot.core import commands
from redbot.core.bot import Red


class SDisable(commands.Cog):
    """Globally disable specific commands for everyone, including the owner."""

    def __init__(self, bot: Red):
        self.bot = bot
        # Hardcoded list of commands to disable globally
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
        bot.add_check(self._disable_check)

    def cog_unload(self):
        try:
            self.bot.remove_check(self._disable_check)
        except Exception:
            pass

    async def _disable_check(self, ctx: commands.Context) -> bool:
        """Block commands if they are in the disabled list."""
        if ctx.command and ctx.command.qualified_name.lower() in self.globally_disabled:
            return False  # silent fail
        return True


async def setup(bot: Red):
    await bot.add_cog(SDisable(bot))