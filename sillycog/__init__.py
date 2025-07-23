from redbot.core import bot
from .sillycog import SillyCog


def setup(bot: bot.Red):
    bot.add_cog(SillyCog(bot))
