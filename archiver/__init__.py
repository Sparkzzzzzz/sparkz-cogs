from .archiver import Archiver


async def setup(bot):
    await bot.add_cog(Archiver(bot))