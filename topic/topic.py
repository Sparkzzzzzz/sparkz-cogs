from urllib import request
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
        

url = "https://conversation-starter1.p.rapidapi.com/"

headers = {
	"X-RapidAPI-Key": "4cde062ea1msh26fabf868841d38p1e4291jsn80bedfad328e",
	"X-RapidAPI-Host": "conversation-starter1.p.rapidapi.com"
}

response = request.request("GET", url, headers=headers)

print(response.text)
        