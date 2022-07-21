from .meetingplans import MyCog


def setup(bot):
    bot.add_cog(MyCog(bot))