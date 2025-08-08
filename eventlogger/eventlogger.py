import discord
from redbot.core import commands, Config
from redbot.core.bot import Red


class EventLogger(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xABCDEF998877)
        self.config.register_guild(log_channel=None, monitor_channel=None)

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel where logs should be sent."""
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.tick()

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def setmonitorchannel(self, ctx, channel: discord.TextChannel):
        """Set the monitor-only channel (edits/deletes excluded)."""
        await self.config.guild(ctx.guild).monitor_channel.set(channel.id)
        await ctx.tick()

    async def send_log(self, guild, embed: discord.Embed, channel_id: int = None):
        if not channel_id:
            channel_id = await self.config.guild(guild).log_channel()
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild is None:
            return
        monitor_id = await self.config.guild(before.guild).monitor_channel()
        if monitor_id and before.channel.id == monitor_id:
            return
        if before.content == after.content:
            return
        embed = discord.Embed(title="Message Edited", color=discord.Color.orange())
        embed.add_field(name="Channel", value=before.channel.mention)
        embed.add_field(
            name="Author",
            value=f"{before.author.mention} (`{before.author.id}`)",
            inline=False,
        )
        embed.add_field(name="Before", value=before.content or "[empty]", inline=False)
        embed.add_field(name="After", value=after.content or "[empty]", inline=False)
        await self.send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None:
            return
        monitor_id = await self.config.guild(message.guild).monitor_channel()
        if monitor_id and message.channel.id == monitor_id:
            return
        embed = discord.Embed(title="Message Deleted", color=discord.Color.red())
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(
            name="Author",
            value=f"{message.author.mention} (`{message.author.id}`)",
            inline=False,
        )
        embed.add_field(
            name="Content", value=message.content or "[empty]", inline=False
        )
        await self.send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return
        embed = discord.Embed(title="Message Sent", color=discord.Color.green())
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(
            name="Author",
            value=f"{message.author.mention} (`{message.author.id}`)",
            inline=False,
        )
        embed.add_field(
            name="Content", value=message.content or "[empty]", inline=False
        )
        await self.send_log(message.guild, embed)
