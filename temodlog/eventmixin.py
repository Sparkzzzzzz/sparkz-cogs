import discord
from discord.ext import commands
import datetime


class EventMixin:
    async def log_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # Fetch audit logs to find the deleter
        deleter = None
        try:
            async for entry in message.guild.audit_logs(
                limit=5, action=discord.AuditLogAction.message_delete
            ):
                # Match only if entry.target is the same user as the message author
                # and created within 5 seconds of now
                if (
                    entry.target.id == message.author.id
                    and (datetime.datetime.utcnow() - entry.created_at).total_seconds()
                    < 5
                ):
                    deleter = entry.user
                    break
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        if deleter:
            desc = f"Message by **{message.author}** deleted by **{deleter}** in {message.channel.mention}"
        else:
            desc = (
                f"Message by **{message.author}** deleted in {message.channel.mention}"
            )

        embed = discord.Embed(
            title="Message Deleted",
            description=desc,
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow(),
        )
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024], inline=False)

        await self.send_to_log_channel(message.guild, embed)

    async def send_to_log_channel(self, guild: discord.Guild, embed: discord.Embed):
        config = await self.config.guild(guild).all()
        log_channel_id = config.get("log_channel_id")
        if not log_channel_id:
            return
        channel = guild.get_channel(log_channel_id)
        if not channel:
            return
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass
