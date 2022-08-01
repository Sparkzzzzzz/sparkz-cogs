from redbot.core import commands
import discord

class MeetingPlans(commands.Cog):
    """Purges the meeting plans channel!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mycom(self, ctx):
        """Purges the meeting plans channel!"""
        
        from discord import discord
        @client.event
        async def on_message(message):
          if not message.content == ":AnnoyingMiddleFinger:":
            await message.delete()
            await message.author.send(f"You can not send {message.content} in that channel.")