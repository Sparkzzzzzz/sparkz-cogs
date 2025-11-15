from .dmtool import dmtool


async def setup(bot):
    await bot.add_cog(dmtool(bot))
