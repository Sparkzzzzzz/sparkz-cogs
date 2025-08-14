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
        # Store reference to the check so we can remove it
        self._check_ref = self._disable_check
        self.bot.add_check(self._check_ref)

    def cog_unload(self):
        # Always remove the exact same check reference
        try:
            self.bot.remove_check(self._check_ref)
        except Exception:
            pass

    async def _disable_check(self, ctx: commands.Context) -> bool:
        """Block commands if they are in the disabled list."""
        if ctx.command and ctx.command.qualified_name.lower() in self.globally_disabled:
            return False
        return True


async def setup(bot: Red):
    await bot.add_cog(SDisable(bot))