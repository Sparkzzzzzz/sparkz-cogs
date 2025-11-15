from .dmtool import DMTool


async def setup(bot):
    await bot.add_cog(DMTool(bot))
