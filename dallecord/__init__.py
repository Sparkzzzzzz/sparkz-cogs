from .dallecord import DalleCord


def setup(bot):
    bot.add_cog(DalleCord(bot))