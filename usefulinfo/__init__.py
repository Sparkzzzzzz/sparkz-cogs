from .usefulinfo import UsefulInfo
import discord


def setup(bot):
    bot.add_cog(UsefulInfo(bot))
