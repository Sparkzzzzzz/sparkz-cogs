from .temodlog import TeModLog


async def setup(bot):
    await bot.add_cog(TeModLog(bot))