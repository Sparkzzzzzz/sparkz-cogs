from .meetingplans import MeetingPlans
import discord


def setup(bot):
    bot.add_cog(MeetingPlans(bot))
