import discord
from discord import client
import random
from redbot.core import commands

class Topic(commands.Cog):
    """Sends a random conversation initiating topic when invoked!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def topic(self, ctx):
     """Sends a random conversation initiating topic when invoked."""
     await ctx.channel.send(random.choice(msg_list))
     msg_list = ["What is something you can tell me about yourself that will help me remember you over others?", "Some believe that our identity is directly correlated to our career. What is your thought?", "What is the most difficult thing for you about living in this city?", "If money wasn’t a necessity, what career would you choose for yourself?", "How do you separate what joy is from happiness?", "What’s your favorite restaurant and why?", "Name three words that best describe you.", "What’s the best Wi-Fi network name you have ever seen?", "What candy bar would you be?", "If you could hack any computer, whose computer would you pick?"]
    
        