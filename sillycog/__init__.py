from redbot.core import bot
from .sillycog import SillyCog


async def setup(bot):
    await bot.add_cog(SillyCog(bot))