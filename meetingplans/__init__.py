from .meetingplans import MeetingPlans


def setup(bot):
    bot.add_cog(MeetingPlans(bot))
