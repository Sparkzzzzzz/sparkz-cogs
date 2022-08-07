import discord
from discord import client
from redbot.core import commands

class Topic(commands.Cog):
    """Sends a random conversation initiating topic when invoked!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def topic(self, ctx):
        """Sends a random conversation initiating topic when invoked!!"""
        
        @client.event
        async def on_message(message):
          if not message.content == ":AnnoyingMiddleFinger:":
            await message.delete()
            await message.author.send(f"You can not send {message.content} in that channel.")