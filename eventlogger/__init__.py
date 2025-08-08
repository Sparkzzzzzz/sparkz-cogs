from .eventlogger import EventLogger


async def setup(bot):
    await bot.add_cog(EventLogger(bot))
