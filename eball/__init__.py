from .eball import eball
import discord
import random

def setup(bot):
    bot.add_cog(eball(bot))
