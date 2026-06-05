from .execute import Execute


async def setup(bot):
    await bot.add_cog(Execute(bot))