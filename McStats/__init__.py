from .mcstats import MCStats  # import the class


#
async def setup(bot):
    await bot.add_cog(MCStats(bot))  # use the correct class name
