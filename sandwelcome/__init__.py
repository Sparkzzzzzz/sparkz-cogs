from .sandwelcome import SandWelcome


async def setup(bot):
    await bot.add_cog(SandWelcome(bot))
