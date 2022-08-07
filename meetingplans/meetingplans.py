from asyncio.streams import _ClientConnectedCallback
import discord
from discord import client
from redbot.core import commands

class MeetingPlans(commands.Cog):
    """Purges the meeting plans channel!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def info(self, ctx):
        """Purges the meeting plans channel!"""
        
        @_ClientConnectedCallback.event
        async def on_message(message):
          if not message.content == ":AnnoyingMiddleFinger:":
            await message.delete()
            await message.author.send(f"You can not send {message.content} in that channel.")