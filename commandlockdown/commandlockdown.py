from redbot.core import commands, Config
from redbot.core.bot import Red
import discord


class CommandLockdown(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069, force_registration=True)
        self.config.register_guild(
            lockdown=False, trusted_roles={}, semi_trusted_roles={}
        )

        bot.add_check(self.global_block_check)

    async def global_block_check(self, ctx: commands.Context):
        if ctx.guild is None:
            return True  # allow in DMs
        if await self.bot.is_owner(ctx.author):
            return True
        lockdown = await self.config.guild(ctx.guild).lockdown()
        if not lockdown:
            return True

        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        semi_trusted_roles = await self.config.guild(ctx.guild).semi_trusted_roles()

        user_role_ids = {r.id for r in ctx.author.roles}
        if any(rid in trusted_roles for rid in user_role_ids):
            return True

        # semi-trusted: check if current cog is allowed
        for rid in user_role_ids:
            allowed_cogs = semi_trusted_roles.get(str(rid), [])
            if "all" in allowed_cogs or ctx.cog.qualified_name in allowed_cogs:
                return True

        return False  # block silently

    @commands.group(name="cl", aliases=["cmdlock"], invoke_without_command=True)
    @commands.guild_only()
    async def cl(self, ctx: commands.Context):
        """Manage command lockdown."""
        lockdown = await self.config.guild(ctx.guild).lockdown()
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        semi_trusted_roles = await self.config.guild(ctx.guild).semi_trusted_roles()

        embed = discord.Embed(
            title="🔒 Command Lockdown",
            description=(
                f"**Status:** {'🟢 Enabled' if lockdown else '🔴 Disabled'}\n"
                f"**Trusted Roles:** {', '.join(f'`{ctx.guild.get_role(rid).name}`' for rid in trusted_roles if ctx.guild.get_role(rid)) or 'None'}\n"
                f"**Semi-Trusted Roles:**\n"
                + "\n".join(
                    f"`{ctx.guild.get_role(int(rid)).name}` → {', '.join(cogs)}"
                    for rid, cogs in semi_trusted_roles.items()
                    if ctx.guild.get_role(int(rid))
                )
                if semi_trusted_roles
                else "None"
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
        """Add or remove a role from full trusted roles."""
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
    async def semi_trust(
        self, ctx: commands.Context, role: discord.Role, *cogs_or_all: str
    ):
        """
        Give a role semi-trusted access to specific cogs or all.
        Example: .cl semi @Role Mod Filter Mutes
        """
        semi_trusted = await self.config.guild(ctx.guild).semi_trusted_roles()
        role_id = str(role.id)
        if not cogs_or_all:
            await ctx.send("⚠️ Please specify cog names or `all`.")
            return
        semi_trusted[role_id] = list(cogs_or_all)
        await self.config.guild(ctx.guild).semi_trusted_roles.set(semi_trusted)
        await ctx.send(f"✅ `{role.name}` now has access to: {', '.join(cogs_or_all)}.")

    @cl.command(name="untrust")
    @commands.has_guild_permissions(administrator=True)
    async def untrust_role(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from trusted or semi-trusted lists."""
        trusted = await self.config.guild(ctx.guild).trusted_roles()
        semi_trusted = await self.config.guild(ctx.guild).semi_trusted_roles()
        role_id_str = str(role.id)
        removed = False
        if role.id in trusted:
            trusted.remove(role.id)
            await self.config.guild(ctx.guild).trusted_roles.set(trusted)
            removed = True
        if role_id_str in semi_trusted:
            semi_trusted.pop(role_id_str)
            await self.config.guild(ctx.guild).semi_trusted_roles.set(semi_trusted)
            removed = True
        if removed:
            await ctx.send(f"✅ `{role.name}` has been untrusted.")
        else:
            await ctx.send(f"ℹ️ `{role.name}` was not trusted.")


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
