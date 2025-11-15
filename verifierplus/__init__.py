from redbot.core import bot
from .verifierplus import VerifierPlus


async def setup(bot):
    await bot.add_cog(VerifierPlus(bot))
