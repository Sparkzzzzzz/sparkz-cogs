from .voting import Voting
import discord

def setup(bot):
    bot.add_cog(Voting(bot))
    
