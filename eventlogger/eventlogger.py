import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from typing import Optional


class EventLogger(commands.Cog):
    """Logs server events except message edits/deletes in the log channel."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=132456)
        self.config.register_guild(
            log_channel=None,
            toggled_events={event: True for event in self.all_events()},
        )

    @staticmethod
    def all_events():
        return [
            "guild_join",
            "guild_remove",
            "member_join",
            "member_remove",
            "member_ban",
            "member_unban",
            "role_create",
            "role_delete",
            "role_update",
            "channel_create",
            "channel_delete",
            "channel_update",
            "emoji_create",
            "emoji_delete",
            "emoji_update",
            "guild_update",
            "message_edit",
            "message_delete",
        ]

    async def get_log_channel(
        self, guild: discord.Guild
    ) -> Optional[discord.TextChannel]:
        channel_id = await self.config.guild(guild).log_channel()
        return guild.get_channel(channel_id)

    async def should_log(
        self,
        guild: discord.Guild,
        event: str,
        channel: Optional[discord.TextChannel] = None,
    ) -> bool:
        toggled = await self.config.guild(guild).toggled_events()
        log_channel = await self.get_log_channel(guild)
        if not toggled.get(event, False):
            return False
        if channel and log_channel and channel.id == log_channel.id:
            if event in ["message_edit", "message_delete"]:
                return False
        return True

    # ======== Commands ========
    @commands.group()
    @commands.guild_only()
    async def eventlog(self, ctx):
        """Base command for EventLogger."""
        pass

    @eventlog.command()
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the log channel."""
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"✅ Event log channel set to {channel.mention}.")

    @eventlog.command()
    async def toggle(self, ctx, event: str):
        """Toggle a specific event on/off."""
        event = event.lower()
        if event not in self.all_events():
            await ctx.send(
                f"❌ Unknown event. Choose from: `{', '.join(self.all_events())}`"
            )
            return
        current = await self.config.guild(ctx.guild).toggled_events()
        current[event] = not current.get(event, True)
        await self.config.guild(ctx.guild).toggled_events.set(current)
        status = "enabled" if current[event] else "disabled"
        await ctx.send(f"✅ `{event}` logging is now {status}.")

    @eventlog.command()
    async def toggleall(self, ctx):
        """Toggle all events at once."""
        current = await self.config.guild(ctx.guild).toggled_events()
        all_on = all(current.values())
        new_state = not all_on
        updated = {e: new_state for e in self.all_events()}
        await self.config.guild(ctx.guild).toggled_events.set(updated)
        status = "enabled" if new_state else "disabled"
        await ctx.send(f"✅ All event logging is now {status}.")

    @eventlog.command(name="settings")
    async def _settings(self, ctx):
        """Show current log settings."""
        log_channel = await self.get_log_channel(ctx.guild)
        toggled = await self.config.guild(ctx.guild).toggled_events()
        enabled = [e for e, v in toggled.items() if v]
        disabled = [e for e, v in toggled.items() if not v]
        embed = discord.Embed(
            title="🛠 Event Logger Settings", color=discord.Color.blurple()
        )
        embed.add_field(
            name="Log Channel",
            value=log_channel.mention if log_channel else "Not Set",
            inline=False,
        )
        embed.add_field(
            name="Enabled Events", value=", ".join(enabled) or "None", inline=False
        )
        embed.add_field(
            name="Disabled Events", value=", ".join(disabled) or "None", inline=False
        )
        await ctx.send(embed=embed)

    # ======== Event Handlers ========

    async def send_log(self, guild: discord.Guild, content: str):
        log_channel = await self.get_log_channel(guild)
        if log_channel:
            await log_channel.send(content)

    # Guild events
    async def on_guild_join(self, guild):
        await self.send_if_enabled(guild, "✅ Bot joined a server.")

    async def on_guild_remove(self, guild):
        await self.send_if_enabled(guild, "❌ Bot removed from a server.")

    # Member events
    async def on_member_join(self, member):
        await self.send_if_enabled(member.guild, f"👤 {member} joined.")

    async def on_member_remove(self, member):
        await self.send_if_enabled(member.guild, f"👋 {member} left.")

    async def on_member_ban(self, guild, user):
        await self.send_if_enabled(guild, f"🔨 {user} was banned.")

    async def on_member_unban(self, guild, user):
        await self.send_if_enabled(guild, f"⚖️ {user} was unbanned.")

    # Role events
    async def on_guild_role_create(self, role):
        await self.send_if_enabled(role.guild, f"➕ Role created: `{role.name}`")

    async def on_guild_role_delete(self, role):
        await self.send_if_enabled(role.guild, f"➖ Role deleted: `{role.name}`")

    async def on_guild_role_update(self, before, after):
        await self.send_if_enabled(
            after.guild, f"♻️ Role updated: `{before.name}` → `{after.name}`"
        )

    # Channel events
    async def on_guild_channel_create(self, channel):
        await self.send_if_enabled(
            channel.guild, f"📁 Channel created: {channel.mention}"
        )

    async def on_guild_channel_delete(self, channel):
        await self.send_if_enabled(
            channel.guild, f"📁 Channel deleted: `{channel.name}`"
        )

    async def on_guild_channel_update(self, before, after):
        await self.send_if_enabled(
            after.guild, f"📁 Channel updated: `{before.name}` → `{after.name}`"
        )

    # Emoji events
    async def on_guild_emojis_update(self, guild, before, after):
        if not await self.should_log(guild, "emoji_update"):
            return
        if len(before) < len(after):
            added = set(after) - set(before)
            for emoji in added:
                await self.send_log(guild, f"😃 Emoji added: {emoji}")
        elif len(before) > len(after):
            removed = set(before) - set(after)
            for emoji in removed:
                await self.send_log(guild, f"😢 Emoji removed: `{emoji.name}`")
        else:
            await self.send_log(guild, f"🌀 Emoji updated.")

    async def on_guild_update(self, before, after):
        await self.send_if_enabled(after, "🏠 Guild settings updated.")

    # Message edits/deletes (excluded in logchannel)
    async def on_message_delete(self, message):
        if message.guild and await self.should_log(
            message.guild, "message_delete", message.channel
        ):
            await self.send_log(
                message.guild,
                f"❌ Message deleted in {message.channel.mention} by {message.author}: `{message.content}`",
            )

    async def on_message_edit(self, before, after):
        if before.guild and await self.should_log(
            before.guild, "message_edit", before.channel
        ):
            await self.send_log(
                before.guild,
                f"✏️ Message edited in {before.channel.mention} by {before.author}:\n**Before:** {before.content}\n**After:** {after.content}",
            )

    async def send_if_enabled(self, guild, content: str, event: Optional[str] = None):
        if event is None:
            # Try inferring the event from caller function name (not always accurate)
            event = inspect.stack()[1].function.replace("on_", "")
        if await self.should_log(guild, event):
            await self.send_log(guild, content)
