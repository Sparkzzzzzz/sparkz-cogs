from .eval import Eval


async def setup(bot):
    await bot.add_cog(Eval(bot))
