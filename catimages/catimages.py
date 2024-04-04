import discord
from redbot.core import commands
import random
import requests

API_KEY = "live_Rx7quM8sNpS39mo8l3IaBLFgCwiy2N28OdwupnXRuLbTVSFVrXXktIwAUh1OODSA"
API_URL = "https://api.thecatapi.com/v1/images/search"

class CatImages(commands.Cog):
    """Post random images of cats!"""

    def __init__(self, bot):
        self.bot = bot
        
    @commands.command()
    async def cat(ctx):
        headers = {"x-api-key": API_KEY}
        response = requests.get(API_URL, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                image_url = data[0]['url']
                await ctx.channel.send(image_url)
            else:
                await ctx.channel.send("No cat images found.")
        else:
            await ctx.channel.send("Failed to fetch cat image. Please try again later.")