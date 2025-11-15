from .taskpacket import taskpacket


async def setup(bot):
    await bot.add_cog(taskpacket(bot))
