from .replier import Replier


async def setup(bot):
    await bot.add_cog(Replier(bot))
