from .sdisable import SDisable


async def setup(bot):
    await bot.add_cog(SDisable(bot))