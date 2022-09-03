import requests
import discord
from discord import client
from redbot.core import commands

class SccEval(commands.Cog):
    """Owner only custom commands!"""

    def __init__(self, bot):
        self.bot = bot
        
    @commands.command()
    @commands.is_owner()
    async def uthere(self, ctx):
      """verifies bot presence"""
      await ctx.channel.send("I am here at your service <@777788426714873877>!")
      
    @commands.command()
    @commands.is_owner()
    async def verifyme(self, ctx):
      """verifies that the user running the command is the bot owner"""
      await ctx.channel.send("<@777788426714873877> you are Sparkz sir, my dear bot owner.")


   