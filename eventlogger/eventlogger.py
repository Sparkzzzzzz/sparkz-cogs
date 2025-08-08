from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from discord.ext.commands import Context
from discord import Embed, Message, Guild, TextChannel, Member
import discord
import datetime


class EventLogger(commands.Cog):
    """Log server events excluding message edits/deletes in the log channel"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9384729384)
        default_guild = {
            "log_channel": None,
            "enabled": {
                "member_join": True,
                "member_remove": True,
                "ban": True,
                "unban": True,
                "channel_create": True,
                "channel_delete": True,
                "channel_update": True,
                "role_create": True,
                "role_delete": True,
                "role_update": True,
                "guild_update": True,
                "emoji_update": True,
                "message_edit": True,
                "message_delete": True,
            },
        }
        self.config.register_guild(**default_guild)

    def _should_log(self, guild: Guild, event: str) -> bool:
        return self.config.guild(guild).enabled.get_attr(event)()

    async def _log(self, guild: Guild, embed: Embed):
        log_channel_id = await self.config.guild(guild).log_channel()
        if log_channel_id:
            channel = guild.get_channel(log_channel_id)
            if channel and isinstance(channel, TextChannel):
                await channel.send(embed=embed)

    def _format_embed(self, title: str, description: str) -> Embed:
        embed = Embed(title=title, description=description, color=discord.Color.blue())
        embed.timestamp = datetime.datetime.utcnow()
        return embed

    # === LOGGING COMMANDS ===

    @commands.group(name="eventlogger", aliases=["elog"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def eventlogger(self, ctx: Context):
        """EventLogger settings"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @eventlogger.command(name="setchannel")
    async def _set_channel(self, ctx: Context, channel: TextChannel):
        """Set the event log channel"""
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"Event log channel set to {channel.mention}")

    @eventlogger.command(name="toggle")
    async def _toggle_event(self, ctx: Context, event: str.lower):
        """Toggle a specific event"""
        current = await self.config.guild(ctx.guild).enabled.get_attr(event)()
        await self.config.guild(ctx.guild).enabled.get_attr(event).set(not current)
        await ctx.send(f"Logging for `{event}` is now set to `{not current}`")

    @eventlogger.command(name="toggleall")
    async def _toggle_all(self, ctx: Context, value: bool):
        """Enable/Disable all event logging"""
        await self.config.guild(ctx.guild).enabled.set(
            {k: value for k in await self.config.guild(ctx.guild).enabled()}
        )
        await ctx.send(f"Logging for all events is now set to `{value}`")

    @eventlogger.command(name="status")
    async def _status(self, ctx: Context):
        """Show enabled/disabled status of events"""
        settings = await self.config.guild(ctx.guild).enabled()
        status_lines = [f"`{k}`: {'✅' if v else '❌'}" for k, v in settings.items()]
        await ctx.send("**Current Event Logging Status:**\n" + "\n".join(status_lines))

    # === EVENT HANDLERS ===

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        if await self._should_log(member.guild, "member_join"):
            embed = self._format_embed(
                "Member Joined", f"{member.mention} joined the server."
            )
            await self._log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        if await self._should_log(member.guild, "member_remove"):
            embed = self._format_embed(
                "Member Left", f"{member.mention} left the server."
            )
            await self._log(member.guild, embed)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        pass  # optional future use

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if await self._should_log(channel.guild, "channel_create"):
            embed = self._format_embed(
                "Channel Created", f"{channel.name} ({channel.id})"
            )
            await self._log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if await self._should_log(channel.guild, "channel_delete"):
            embed = self._format_embed(
                "Channel Deleted", f"{channel.name} ({channel.id})"
            )
            await self._log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if await self._should_log(after.guild, "channel_update"):
            embed = self._format_embed(
                "Channel Updated", f"{before.name} → {after.name}"
            )
            await self._log(after.guild, embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if await self._should_log(after, "guild_update"):
            embed = self._format_embed(
                "Guild Updated", f"Possible server setting changes."
            )
            await self._log(after, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if await self._should_log(role.guild, "role_create"):
            embed = self._format_embed("Role Created", role.name)
            await self._log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if await self._should_log(role.guild, "role_delete"):
            embed = self._format_embed("Role Deleted", role.name)
            await self._log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if await self._should_log(after.guild, "role_update"):
            embed = self._format_embed("Role Updated", f"{before.name} → {after.name}")
            await self._log(after.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        if await self._should_log(guild, "ban"):
            embed = self._format_embed("Member Banned", f"{user.name}")
            await self._log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        if await self._should_log(guild, "unban"):
            embed = self._format_embed("Member Unbanned", f"{user.name}")
            await self._log(guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        guild = before.guild
        if guild is None:
            return
        log_channel_id = await self.config.guild(guild).log_channel()
        if before.channel.id == log_channel_id:
            return
        if await self._should_log(guild, "message_edit"):
            embed = self._format_embed(
                "Message Edited",
                f"Author: {before.author.mention}\nBefore: {before.content}\nAfter: {after.content}",
            )
            await self._log(guild, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: Message):
        guild = message.guild
        if guild is None:
            return
        log_channel_id = await self.config.guild(guild).log_channel()
        if message.channel.id == log_channel_id:
            return
        if await self._should_log(guild, "message_delete"):
            embed = self._format_embed(
                "Message Deleted",
                f"Author: {message.author.mention}\nContent: {message.content}",
            )
            await self._log(guild, embed)
