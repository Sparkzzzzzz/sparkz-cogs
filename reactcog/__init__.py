from .reactcog import ReactCog


async def setup(bot):
    await bot.add_cog(ReactCog(bot))
