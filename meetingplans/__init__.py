from .meetingplans import MeetingPlans
from discord import discord


def setup(bot):
    bot.add_cog(MeetingPlans(bot))
