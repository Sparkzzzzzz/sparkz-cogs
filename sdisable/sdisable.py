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
        # Store removed commands so we can restore on unload
        self._stored_commands = {}
        self._disable_commands()

    def cog_unload(self):
        self._restore_commands()

    def _disable_commands(self):
        """Remove the target commands from the bot."""
        for name in list(self.globally_disabled):
            if name in self._stored_commands:
                continue  # Already removed
            cmd = self.bot.get_command(name)  # use get_command instead of all_commands
            if cmd:
                self._stored_commands[name] = cmd
                self.bot.remove_command(name)

    def _restore_commands(self):
        """Re-add previously removed commands."""
        for name, cmd in self._stored_commands.items():
            self.bot.add_command(cmd, override=True)  # ensure it properly restores
        self._stored_commands.clear()

    @commands.Cog.listener()
    async def on_ready(self):
        # Make sure they're gone even if bot reconnects
        self._disable_commands()


async def setup(bot: Red):
    await bot.add_cog(SDisable(bot))