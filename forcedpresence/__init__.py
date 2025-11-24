from .forcedpresence import ForcePresence


async def setup(bot):
    await bot.add_cog(ForcePresence(bot))
