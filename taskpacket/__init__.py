from .taskpacket import TaskPacket


async def setup(bot):
    await bot.add_cog(TaskPacket(bot))
