from .neilshit import NeilShit
import discord


def setup(bot):
    bot.add_cog(NeilShit(bot))