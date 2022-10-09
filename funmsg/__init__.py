from .funmsg import FunMsg
import discord


def setup(bot):
    bot.add_cog(FunMsg(bot))