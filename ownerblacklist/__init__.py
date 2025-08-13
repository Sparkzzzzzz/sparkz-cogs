from .ownerblacklist import OwnerBlacklist


async def setup(bot):
    await bot.add_cog(OwnerBlacklist(bot))