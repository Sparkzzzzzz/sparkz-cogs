from redbot.core import commands, Config
from .eventmixin import EventMixin


class TeModLog(commands.Cog, EventMixin):
    """Temporary Extended ModLog with fixed deletion tracking."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069, force_registration=True)
        default_guild = {"log_channel_id": None}
        self.config.register_guild(**default_guild)

    @commands.group()
    @commands.guild_only()
    async def temodlog(self, ctx):
        """Manage TeModLog settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @temodlog.command()
    @commands.admin()
    async def setlog(self, ctx, channel: commands.TextChannelConverter):
        """Set the log channel."""
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id)
        await ctx.send(f"Log channel set to {channel.mention}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        await self.log_message_delete(message)
