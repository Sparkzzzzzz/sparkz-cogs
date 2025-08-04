import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from typing import Optional


class CommandLockdown(commands.Cog):
    """Locks down all commands except for owners and trusted roles."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069, force_registration=True)
        self.config.register_guild(lockdown=False, trusted_roles=[])

    async def cog_check(self, ctx: commands.Context):
        if await self.bot.is_owner(ctx.author):
            return True  # Always allow bot owners

        lockdown = await self.config.guild(ctx.guild).lockdown()
        if not lockdown:
            return True  # Lockdown not enabled

        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        if any(role.id in trusted_roles for role in ctx.author.roles):
            return True

        # Silently block
        raise commands.CheckFailure()

    @commands.group(name="commandlockdown", aliases=["cl"])
    @commands.guild_only()
    @commands.admin()
    async def commandlockdown(self, ctx: commands.Context):
        """Manage command lockdown settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @commandlockdown.command(name="toggle")
    async def toggle_lockdown(self, ctx: commands.Context):
        """Toggle command lockdown on or off."""
        current = await self.config.guild(ctx.guild).lockdown()
        await self.config.guild(ctx.guild).lockdown.set(not current)
        status = "enabled" if not current else "disabled"
        await ctx.send(f"🔒 Command lockdown is now **{status}**.")

    @commandlockdown.command(name="addtrusted")
    async def add_trusted_role(self, ctx: commands.Context, role: discord.Role):
        """Add a trusted role allowed to use commands during lockdown."""
        async with self.config.guild(ctx.guild).trusted_roles() as roles:
            if role.id in roles:
                await ctx.send("✅ That role is already trusted.")
                return
            roles.append(role.id)
        await ctx.send(f"✅ Added **{role.name}** to the trusted roles list.")

    @commandlockdown.command(name="removetrusted")
    async def remove_trusted_role(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from the trusted list."""
        async with self.config.guild(ctx.guild).trusted_roles() as roles:
            if role.id not in roles:
                await ctx.send("⚠️ That role isn’t trusted.")
                return
            roles.remove(role.id)
        await ctx.send(f"🗑 Removed **{role.name}** from the trusted roles list.")

    @commandlockdown.command(name="status")
    async def lockdown_status(self, ctx: commands.Context):
        """Check the lockdown status and trusted roles."""
        lockdown = await self.config.guild(ctx.guild).lockdown()
        trusted_ids = await self.config.guild(ctx.guild).trusted_roles()
        trusted_roles = [ctx.guild.get_role(rid) for rid in trusted_ids]
        trusted_roles = [r.mention for r in trusted_roles if r]

        desc = f"🔒 **Lockdown:** {'Enabled' if lockdown else 'Disabled'}\n"
        desc += f"✅ **Trusted Roles:** {', '.join(trusted_roles) if trusted_roles else 'None'}"
        await ctx.send(desc)
