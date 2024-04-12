from .usefulinfo import UsefulInfo

async def setup(bot):
    await bot.add_cog(UsefulInfo(bot))
