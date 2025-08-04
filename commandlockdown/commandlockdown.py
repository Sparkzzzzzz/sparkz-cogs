from redbot.core import commands, Config
from redbot.core.bot import Red
import discord


class CommandLockdown(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069, force_registration=True)
        self.config.register_guild(lockdown=False, trusted_roles=[])

        # Add global check to block commands during lockdown
        bot.add_check(self.global_block_check)

    async def global_block_check(self, ctx: commands.Context):
        if ctx.guild is None:
            return True  # Allow DMs
        if await self.bot.is_owner(ctx.author):
            return True
        lockdown = await self.config.guild(ctx.guild).lockdown()
        if not lockdown:
            return True
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        if any(role.id in trusted_roles for role in ctx.author.roles):
            return True
        return False  # Block command silently

    @commands.group(name="cl", aliases=["cmdlock"], invoke_without_command=True)
    @commands.guild_only()
    async def cl(self, ctx: commands.Context):
        """Manage command lockdown."""
        lockdown = await self.config.guild(ctx.guild).lockdown()
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        embed = discord.Embed(
            title="🔒 Command Lockdown",
            description=(
                f"**Status:** {'🟢 Enabled' if lockdown else '🔴 Disabled'}\n"
                f"**Trusted Roles:** {', '.join(f'<@&{rid}>' for rid in trusted_roles) if trusted_roles else 'None'}"
            ),
            color=discord.Color.red() if lockdown else discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @cl.command(name="toggle")
    @commands.has_guild_permissions(administrator=True)
    async def toggle_lockdown(self, ctx: commands.Context):
        """Toggle command lockdown on/off."""
        current = await self.config.guild(ctx.guild).lockdown()
        await self.config.guild(ctx.guild).lockdown.set(not current)
        status = "enabled 🔒" if not current else "disabled 🔓"
        await ctx.send(f"Command lockdown is now **{status}**.")

    @cl.command(name="trust")
    @commands.has_guild_permissions(administrator=True)
    async def trust_role(self, ctx: commands.Context, role: discord.Role):
        """Add or remove a role from trusted roles."""
        trusted = await self.config.guild(ctx.guild).trusted_roles()
        if role.id in trusted:
            trusted.remove(role.id)
            await ctx.send(f"Removed {role.mention} from trusted roles.")
        else:
            trusted.append(role.id)
            await ctx.send(f"Added {role.mention} to trusted roles.")
        await self.config.guild(ctx.guild).trusted_roles.set(trusted)
