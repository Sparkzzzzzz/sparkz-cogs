from .scceval import SccEval
import discord


def setup(bot):
    bot.add_cog(SccEval(bot))
