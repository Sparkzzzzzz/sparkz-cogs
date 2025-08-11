import asyncio
import datetime
import discord
from redbot.core import commands, Config, i18n, modlog
from redbot.core.utils.chat_formatting import box, humanize_list
from red_commons.logging import getLogger
from enum import Enum
from typing import Any, Deque, Dict, Optional
from collections import deque

_ = i18n.Translator("Temodlog", __file__)
logger = getLogger("red.trusty-cogs.Temodlog")


class EventMixin:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567890, force_registration=True
        )
        self.config.register_guild(
            message_delete={"enabled": True, "embed": True, "exclude_bots": True},
            modlog_channel=None,
            ignored_channels=[],
        )
        self._ban_cache: Dict[int, Deque[int]] = {}
        bot.add_listener(self.on_raw_message_delete, "on_raw_message_delete")

    async def modlog_channel(self, guild: discord.Guild):
        ch_id = await self.config.guild(guild).modlog_channel()
        if not ch_id:
            raise RuntimeError("No modlog channel set.")
        channel = guild.get_channel(ch_id)
        if not channel:
            raise RuntimeError("Modlog channel not found.")
        return channel

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        guild = self.bot.get_guild(payload.guild_id)
        if not guild or guild.id not in await self.config.all_guilds():
            return

        settings = await self.config.guild(guild).message_delete()
        if not settings.get("enabled", False):
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel or payload.message_id is None:
            return

        # Attempt to fetch the deleted message if cached
        if payload.cached_message:
            message = payload.cached_message
        else:
            if settings.get("exclude_bots", False):
                return
            # Cannot retrieve content
            message = None

        # Wait a short moment for the audit log to register the deletion
        await asyncio.sleep(1.0)

        deleter = None
        if guild.me.guild_permissions.view_audit_log:
            try:
                async for entry in guild.audit_logs(
                    limit=5, action=discord.AuditLogAction.message_delete
                ):
                    if (
                        message
                        and entry.target.id == message.author.id
                        and entry.extra.channel.id == channel.id
                        and (
                            datetime.datetime.utcnow() - entry.created_at
                        ).total_seconds()
                        < 5
                    ):
                        deleter = entry.user
                        break
            except Exception:
                logger.exception("Failed fetching audit log entry for message delete.")

        embed = discord.Embed(
            title="Message Deleted",
            color=discord.Color.red(),
            timestamp=(
                payload.cached_message.created_at
                if payload.cached_message
                else datetime.datetime.utcnow()
            ),
        )

        if message and message.content:
            embed.add_field(name="Content", value=message.content[:1024], inline=False)

        desc = f"Channel: {channel.mention}\n"
        if message:
            desc += f"Author: {message.author.mention}\n"
        if deleter:
            desc += f"Deleted by: {deleter.mention}"
        elif message:
            desc += "Deleted by: Unknown or self-deleted"
        else:
            desc += "Deleted by: Unknown"

        embed.description = desc

        try:
            modchan = await self.modlog_channel(guild)
            await modchan.send(embed=embed)
        except Exception:
            pass
