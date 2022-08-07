from .topic import Topic
import discord


def setup(bot):
    bot.add_cog(Topic(bot))
