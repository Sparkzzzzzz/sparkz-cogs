from .channelrestrict import ChannelRestrict


async def setup(bot):
    await bot.add_cog(ChannelRestrict(bot))