from .licenseinfo import LicenseInfo
import discord


def setup(bot):
    bot.add_cog(LicenseInfo(bot))
