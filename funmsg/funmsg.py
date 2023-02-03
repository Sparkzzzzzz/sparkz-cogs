import discord
from redbot.core import commands

class FunMsg(commands.cog):
    """sends a conversation initiation message."""

    def __init__(self, bot):
        self.bot = bot