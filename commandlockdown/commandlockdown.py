from redbot.core import commands, Config
from redbot.core.bot import Red
import discord


class CommandLockdown(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069, force_registration=True)
        self.config.register_guild(
            lockdown=False,
            trusted_roles=[],  # Full access
            semi_trusted_roles={},  # Cog-specific access
        )

        bot.add_check(self.global_block_check)

    async def global_block_check(self, ctx: commands.Context):
        if ctx.guild is None:
            return True
        if await self.bot.is_owner(ctx.author):
            return True

        lockdown = await self.config.guild(ctx.guild).lockdown()
        if not lockdown:
            return True

        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        if any(role.id in trusted_roles for role in ctx.author.roles):
            return True

        semi_trusted_roles = await self.config.guild(ctx.guild).semi_trusted_roles()
        for role in ctx.author.roles:
            allowed_cogs = semi_trusted_roles.get(str(role.id), [])
            if ctx.cog and (
                ctx.cog.qualified_name in allowed_cogs or "all" in allowed_cogs
            ):
                return True

        return False

    @commands.group(name="cl", aliases=["cmdlock"], invoke_without_command=True)
    @commands.guild_only()
    async def cl(self, ctx: commands.Context):
        """Manage command lockdown."""
        lockdown = await self.config.guild(ctx.guild).lockdown()
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        semi_trusted_roles = await self.config.guild(ctx.guild).semi_trusted_roles()

        def role_name(rid):
            role = ctx.guild.get_role(rid)
            return role.name if role else f"(deleted role {rid})"

        embed = discord.Embed(
            title="🔒 Command Lockdown",
            description=(
                f"**Status:** {'🟢 Enabled' if lockdown else '🔴 Disabled'}\n\n"
                f"**Full Trusted Roles:** {', '.join(role_name(r) for r in trusted_roles) if trusted_roles else 'None'}\n"
                f"**Semi-Trusted Roles:** {', '.join(f'{role_name(int(r))}: {', '.join(cogs)}' for r, cogs in semi_trusted_roles.items()) if semi_trusted_roles else 'None'}"
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
        await ctx.send(f"Lockdown is now **{status}**.")

    @cl.command(name="trust")
    @commands.has_guild_permissions(administrator=True)
    async def trust_role(self, ctx: commands.Context, role: discord.Role):
        """Add/remove a role from full trusted roles."""
        trusted = await self.config.guild(ctx.guild).trusted_roles()
        if role.id in trusted:
            trusted.remove(role.id)
            await ctx.send(f"❌ `{role.name}` removed from full trusted roles.")
        else:
            trusted.append(role.id)
            await ctx.send(f"✅ `{role.name}` now has **full access** during lockdown.")
        await self.config.guild(ctx.guild).trusted_roles.set(trusted)

    @cl.command(name="semi")
    @commands.has_guild_permissions(administrator=True)
    async def semi_trust_role(self, ctx: commands.Context, role: discord.Role, *cogs):
        """Give a role access to only specific cogs during lockdown."""
        semi_trusted = await self.config.guild(ctx.guild).semi_trusted_roles()
        role_id_str = str(role.id)
        if not cogs:
            if role_id_str in semi_trusted:
                semi_trusted.pop(role_id_str)
                await ctx.send(f"❌ `{role.name}` removed from semi-trusted roles.")
            else:
                await ctx.send("❗ No cogs specified to trust.")
        else:
            semi_trusted[role_id_str] = list(cogs)
            await ctx.send(
                f"✅ `{role.name}` now has access to: {', '.join(cogs)} during lockdown."
            )

        await self.config.guild(ctx.guild).semi_trusted_roles.set(semi_trusted)
