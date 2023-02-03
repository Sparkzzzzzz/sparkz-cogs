from redbot.core import commands

class DalleCord(commands.Cog):
    """A cog which allows you to use dalle imgen in discord!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def imagine(self, ctx):
        """Give dalle a promt to generate an image!"""
        