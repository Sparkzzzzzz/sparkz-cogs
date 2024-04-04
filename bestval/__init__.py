from .bestval import BestVal
import discord


def setup(bot):
    bot.add_cog(BestVal(bot))