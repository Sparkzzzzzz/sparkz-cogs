import requests
import discord
from discord import client
from redbot.core import commands

class UsefulInfo(commands.Cog):
    """Useful Info!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def creator(ctx):
     await ctx.channel.send("I was made by my bot owner **Sparkz#2645**!")
    
    @commands.command()
    async def version(ctx):
     await ctx.channel.send("version: `0.0.1`")   