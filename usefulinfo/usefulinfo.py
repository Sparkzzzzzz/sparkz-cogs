import discord
from discord import client
from redbot.core import commands

class UsefulInfo(commands.Cog):
    """Useful Info!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def creator(self, ctx):
        """Tells who made the bot."""
        await ctx.channel.send(
            "I was made by my super cute and handsome bot dev <@777788426714873877>."
        )

    @commands.command()
    async def version(self, ctx):
        """Tells the current bot version."""
        await ctx.channel.send("version: `0.0.1`")   

    @commands.command()
    async def dev(self, ctx):
        """Tells if the bot is in development."""
        await ctx.channel.send("I was made by my super cute and handsome bot dev <@777788426714873877>.")
