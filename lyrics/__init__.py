from .lyrics import Lyrics

async def setup(bot):
    await bot.add_cog(Lyrics(bot))