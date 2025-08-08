from .eventlogger import EventLogger


def setup(bot):
    bot.add_cog(EventLogger(bot))
