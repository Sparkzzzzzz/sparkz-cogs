import discord
from redbot.core import commands
from redbot.core.bot import Red


class SDisable(commands.Cog):
    """Completely remove specific commands from Red for everyone, including owner."""

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

        # Remove them right away if loaded after Core
        self._remove_disabled_commands()

        # Listen for future command registrations (if Core reloads, etc.)
        bot.add_listener(self._on_command_add, "on_command_add")

    def cog_unload(self):
        self.bot.remove_listener(self._on_command_add, "on_command_add")

    def _remove_disabled_commands(self):
        """Permanently remove blocked commands from the bot's registry."""
        to_remove = [
            name for name in self.globally_disabled if name in self.bot.all_commands
        ]
        for name in to_remove:
            cmd = self.bot.all_commands.pop(name, None)
            if cmd:
                for alias in list(cmd.aliases):
                    self.bot.all_commands.pop(alias, None)

    async def _on_command_add(self, command: commands.Command):
        """Whenever a new command is added, remove it if it's disabled."""
        if command.qualified_name.lower() in self.globally_disabled:
            # Remove from bot immediately
            self.bot.all_commands.pop(command.qualified_name, None)
            for alias in list(command.aliases):
                self.bot.all_commands.pop(alias, None)

    async def _disable_check(self, ctx: commands.Context) -> bool:
        """Extra safety check to prevent execution (shouldn't be needed if removed)."""
        if ctx.command and ctx.command.qualified_name.lower() in self.globally_disabled:
            return False
        return True


async def setup(bot: Red):
    await bot.add_cog(SDisable(bot))
