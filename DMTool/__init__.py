from .dmtool import DMTool  # import the class


async def setup(bot):
    await bot.add_cog(DMTool(bot))  # use the class name
