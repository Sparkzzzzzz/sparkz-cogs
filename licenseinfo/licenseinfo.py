import requests
import discord
from discord import client
from redbot.core import commands

class LicenseInfo(commands.Cog):
    """Modifies the core licenseinfo command!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def licenseinfo(ctx):
     await ctx.channel.send("Made by Sparkz!")
        