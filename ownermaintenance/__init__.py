from .ownermaintenance import OwnerMaintenance


async def setup(bot):
    await bot.add_cog(OwnerMaintenance(bot))
