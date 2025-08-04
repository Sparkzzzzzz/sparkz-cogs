from .logchannel import LogChannel


async def setup(bot):
    await bot.add_cog(LogChannel(bot))
