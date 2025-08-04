from .commandlockdown import CommandLockdown


async def setup(bot):
    await bot.add_cog(CommandLockdown(bot))
