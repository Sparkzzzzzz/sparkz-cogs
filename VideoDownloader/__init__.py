from .videodownloader import VideoDownloader


async def setup(bot):
    await bot.add_cog(VideoDownloader(bot))
