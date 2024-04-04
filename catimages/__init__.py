from .catimages import CatImages
import requests

async def setup(bot):
    await bot.add_cog(CatImages(bot))