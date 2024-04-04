from .bestval import BestVal

async def setup(bot):
    await bot.add_cog(BestVal(bot))