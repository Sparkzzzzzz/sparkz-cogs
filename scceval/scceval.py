import requests
import discord
from discord import client
from redbot.core import commands

class SccEval(commands.Cog):
    """Owner only custom commands!"""

    def __init__(self, bot):
        self.bot = bot
        
    @client.command()
    @commands.is_owner()
    async def uthere(ctx):
      await ctx.channel.send("I am here at your service <@777788426714873877>")
      
    @client.command()
    @commands.is_owner()
    async def verifyme(ctx):
      await ctx.channel.send("<@777788426714873877> you are Sparkz, sir, my dear bot owner.")


   