import discord
from redbot.core import commands, Config


class CommandLockdown(commands.Cog):
    """Lockdown bot commands to certain roles."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=987654321, force_registration=True
        )
        self.config.register_guild(lockdown_enabled=False, trusted_roles={})

    async def red_delete_data_for_user(self, **kwargs):
        return

    async def cog_check(self, ctx):
        """Global check for lockdown."""
        # Always allow owners
        if await self.bot.is_owner(ctx.author):
            return True

        guild = ctx.guild
        if not guild:
            return True  # Allow in DMs

        data = await self.config.guild(guild).all()
        if not data["lockdown_enabled"]:
            return True

        trusted_roles = data["trusted_roles"]
        author_roles = {r.id for r in ctx.author.roles}

        for role_id, cogs in trusted_roles.items():
            if role_id in author_roles:
                allowed_cogs = [c.lower() for c in cogs]
                if "all" in allowed_cogs:
                    return True
                if ctx.cog and ctx.cog.qualified_name.lower() in allowed_cogs:
                    return True

        return False

    @commands.group()
    @commands.guild_only()
    @commands.admin()
    async def cl(self, ctx):
        """Command Lockdown controls."""

    @cl.command()
    async def toggle(self, ctx):
        """Toggle lockdown mode."""
        current = await self.config.guild(ctx.guild).lockdown_enabled()
        await self.config.guild(ctx.guild).lockdown_enabled.set(not current)
        await ctx.send(f"🔒 Lockdown mode {'enabled' if not current else 'disabled'}.")

    @cl.command()
    async def status(self, ctx):
        """Show lockdown status."""
        data = await self.config.guild(ctx.guild).all()
        lockdown = data["lockdown_enabled"]
        trusted_roles = data["trusted_roles"]

        embed = discord.Embed(
            title="Command Lockdown Status", color=discord.Color.blurple()
        )
        embed.add_field(
            name="Lockdown Enabled",
            value="✅ Yes" if lockdown else "❌ No",
            inline=False,
        )

        if trusted_roles:
            role_lines = []
            for role_id, cogs in trusted_roles.items():
                role = ctx.guild.get_role(role_id)
                role_name = role.name if role else f"(Unknown Role {role_id})"
                cogs_str = ", ".join(cogs) if cogs else "None"
                role_lines.append(f"**{role_name}** → {cogs_str}")
            embed.add_field(
                name="Trusted Roles", value="\n".join(role_lines), inline=False
            )
        else:
            embed.add_field(name="Trusted Roles", value="None", inline=False)

        await ctx.send(embed=embed)

    @cl.command()
    async def trust(self, ctx, role: discord.Role, *cogs):
        """Trust a role for certain cogs during lockdown. Use 'all' for all cogs."""
        data = await self.config.guild(ctx.guild).trusted_roles()
        data[role.id] = list(cogs) if cogs else ["all"]
        await self.config.guild(ctx.guild).trusted_roles.set(data)
        await ctx.send(
            f"✅ Role **{role.name}** trusted for: {', '.join(cogs) if cogs else 'all'}."
        )

    @cl.command()
    async def untrust(self, ctx, role: discord.Role):
        """Remove a trusted role."""
        data = await self.config.guild(ctx.guild).trusted_roles()
        if role.id in data:
            del data[role.id]
            await self.config.guild(ctx.guild).trusted_roles.set(data)
            await ctx.send(f"❌ Role **{role.name}** removed from trusted list.")
        else:
            await ctx.send("That role is not trusted.")


async def setup(bot):
    await bot.add_cog(CommandLockdown(bot))
