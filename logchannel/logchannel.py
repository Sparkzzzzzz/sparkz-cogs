import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
import datetime


class LogChannel(commands.Cog):
    """Log message edits and deletes from one channel to another."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "source_channel": None,
            "log_channel": None,
        }
        self.config.register_guild(**default_guild)

    @commands.group()
    @commands.guild_only()
    async def logchannel(self, ctx):
        """Configure source and log channels."""
        pass

    @logchannel.command(name="setsource")
    async def set_source(self, ctx, channel: discord.TextChannel):
        """Set the source channel to monitor for edits/deletes."""
        await self.config.guild(ctx.guild).source_channel.set(channel.id)
        await ctx.send(f"✅ Source channel set to {channel.mention}")

    @logchannel.command(name="settarget")
    async def set_target(self, ctx, channel: discord.TextChannel):
        """Set the target log channel."""
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"✅ Log channel set to {channel.mention}")

    async def send_log(self, guild: discord.Guild, embed: discord.Embed):
        log_id = await self.config.guild(guild).log_channel()
        if log_id is None:
            return
        log_channel = guild.get_channel(log_id)
        if log_channel:
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return

        source_id = await self.config.guild(before.guild).source_channel()
        if before.channel.id != source_id:
            return
        if before.content == after.content:
            return  # Ignore embed updates or invisible changes

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(
            name="Author",
            value=f"{before.author.mention} (`{before.author.id}`)",
            inline=True,
        )
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(
            name="Before", value=before.content[:1024] or "*empty*", inline=False
        )
        embed.add_field(
            name="After", value=after.content[:1024] or "*empty*", inline=False
        )
        embed.set_footer(text=f"Message ID: {before.id}")

        await self.send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        source_id = await self.config.guild(message.guild).source_channel()
        if message.channel.id != source_id:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(
            name="Author",
            value=f"{message.author.mention} (`{message.author.id}`)",
            inline=True,
        )
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(
            name="Content", value=message.content[:1024] or "*empty*", inline=False
        )
        embed.set_footer(text=f"Message ID: {message.id}")

        await self.send_log(message.guild, embed)
