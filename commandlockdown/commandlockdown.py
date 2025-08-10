import discord
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import box


class CommandLockdown(commands.Cog):
    """Lock down commands during special situations."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1374786420241203302)
        self.config.register_guild(
            lockdown_enabled=False,
            trusted_roles={},  # {role_id: ["all"] or ["CogName", ...]}
        )
        self.bot.add_check(self.global_lockdown_check)

    def cog_unload(self):
        # Remove the global check when cog unloads so commands aren't blocked
        self.bot.remove_check(self.global_lockdown_check)

    async def global_lockdown_check(self, ctx: commands.Context):
        """Global check to block commands if lockdown is enabled."""
        if await self.bot.is_owner(ctx.author):
            return True  # Owner bypass
        guild = ctx.guild
        if guild is None:
            return True  # Allow in DMs
        lockdown = await self.config.guild(guild).lockdown_enabled()
        if not lockdown:
            return True  # No lockdown, allow
        trusted_roles = await self.config.guild(guild).trusted_roles()
        user_roles = {str(r.id) for r in ctx.author.roles}
        for rid, allowed_cogs in trusted_roles.items():
            if str(rid) in user_roles:
                if "all" in allowed_cogs:
                    return True
                if ctx.cog and ctx.cog.qualified_name in allowed_cogs:
                    return True
        return False

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def cl(self, ctx):
        """Command Lockdown management."""
        pass

    @cl.command()
    async def toggle(self, ctx):
        """Toggle lockdown on or off."""
        guild = ctx.guild
        current = await self.config.guild(guild).lockdown_enabled()
        await self.config.guild(guild).lockdown_enabled.set(not current)
        await ctx.send(f"Lockdown {'enabled' if not current else 'disabled'}.")

    @cl.command()
    async def trust(self, ctx, role: discord.Role, *cogs_or_all: str):
        """Trust a role with all or specific cogs."""
        guild = ctx.guild
        trusted_roles = await self.config.guild(guild).trusted_roles()
        trusted_roles[str(role.id)] = (
            ["all"] if "all" in cogs_or_all else list(cogs_or_all)
        )
        await self.config.guild(guild).trusted_roles.set(trusted_roles)
        await ctx.send(
            f"Trusted **{role.name}** with {', '.join(trusted_roles[str(role.id)])}."
        )

    @cl.command()
    async def untrust(self, ctx, role: discord.Role):
        """Remove a role from trusted list."""
        guild = ctx.guild
        trusted_roles = await self.config.guild(guild).trusted_roles()
        if str(role.id) in trusted_roles:
            del trusted_roles[str(role.id)]
            await self.config.guild(guild).trusted_roles.set(trusted_roles)
            await ctx.send(f"Removed trust for **{role.name}**.")
        else:
            await ctx.send(f"**{role.name}** was not trusted.")

    @cl.command()
    async def status(self, ctx):
        """Show lockdown status and trusted roles."""
        guild = ctx.guild
        lockdown = await self.config.guild(guild).lockdown_enabled()
        trusted_roles = await self.config.guild(guild).trusted_roles()
        desc = f"**Lockdown:** {'Enabled' if lockdown else 'Disabled'}\n\n"
        if trusted_roles:
            desc += "**Trusted Roles:**\n"
            for rid, cogs in trusted_roles.items():
                role = guild.get_role(int(rid))
                role_name = role.name if role else f"Unknown({rid})"
                desc += f"- {role_name}: {', '.join(cogs)}\n"
        else:
            desc += "No trusted roles."
        await ctx.send(box(desc, lang="ini"))
