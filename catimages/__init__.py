from .catimages import CatImages

async def setup(bot):
    await bot.add_cog(CatImages(bot))