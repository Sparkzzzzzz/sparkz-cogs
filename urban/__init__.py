from .urban import Urban


async def setup(bot):
    await bot.add_cog(Urban(bot))