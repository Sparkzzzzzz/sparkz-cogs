import discord
from discord.ext import commands
from redbot.core import commands as redcommands, Config, checks


class CommandLockdown(commands.Cog):
    """Lock down bot commands to certain roles."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567890, force_registration=True
        )
        default_guild = {"lockdown": False, "trusted_roles": {}}  # role_id: [cog names]
        self.config.register_guild(**default_guild)

    def cog_check(self, ctx):
        # Allow bot owner at all times
        if ctx.author.id in self.bot.owner_ids:
            return True

        # Only allow CL commands if bot owner
        if ctx.command.qualified_name.startswith("cl"):
            return False

        return True

    async def cog_before_invoke(self, ctx):
        # Lockdown logic for all commands except CL itself
        if ctx.command.qualified_name.startswith("cl"):
            return

        guild_conf = await self.config.guild(ctx.guild).all()
        if guild_conf["lockdown"]:
            # Check trusted roles
            trusted_roles = guild_conf["trusted_roles"]
            user_role_ids = {r.id for r in ctx.author.roles}
            allowed_cogs = set()

            for rid, cogs in trusted_roles.items():
                if int(rid) in user_role_ids:
                    allowed_cogs.update(cogs)

            # Allow only if the cog is trusted
            if ctx.cog and ctx.cog.qualified_name in allowed_cogs:
                return
            raise commands.CheckFailure(
                "Lockdown in effect. You are not allowed to use this command."
            )

    @redcommands.group(name="cl")
    @checks.is_owner()
    async def cl_group(self, ctx):
        """Command Lockdown settings."""
        pass

    @cl_group.command(name="toggle")
    async def cl_toggle(self, ctx):
        """Toggle lockdown mode."""
        guild_conf = await self.config.guild(ctx.guild).all()
        new_status = not guild_conf["lockdown"]
        await self.config.guild(ctx.guild).lockdown.set(new_status)
        await ctx.send(f"🔒 Lockdown {'enabled' if new_status else 'disabled'}.")

    @cl_group.command(name="trust")
    async def cl_trust_role(self, ctx, role: discord.Role, *cogs: str):
        """Trust a role for specific cogs."""
        guild_conf = await self.config.guild(ctx.guild).trusted_roles()
        role_id = str(role.id)
        if role_id not in guild_conf:
            guild_conf[role_id] = []
        for cog in cogs:
            if cog not in guild_conf[role_id]:
                guild_conf[role_id].append(cog)
        await self.config.guild(ctx.guild).trusted_roles.set(guild_conf)
        await ctx.send(f"✅ Trusted role **{role.name}** for cogs: {', '.join(cogs)}")

    @cl_group.command(name="untrust")
    async def cl_untrust_role(self, ctx, role: discord.Role):
        """Remove a trusted role."""
        guild_conf = await self.config.guild(ctx.guild).trusted_roles()
        role_id = str(role.id)
        if role_id in guild_conf:
            del guild_conf[role_id]
            await self.config.guild(ctx.guild).trusted_roles.set(guild_conf)
            await ctx.send(f"🚫 Removed trusted role **{role.name}**.")
        else:
            await ctx.send(f"⚠️ Role **{role.name}** is not trusted.")

    @cl_group.command(name="status")
    async def cl_status(self, ctx):
        """Show lockdown status and trusted roles."""
        guild_conf = await self.config.guild(ctx.guild).all()
        lockdown_status = "ON 🔒" if guild_conf["lockdown"] else "OFF 🔓"
        trusted_roles = guild_conf["trusted_roles"]

        if trusted_roles:
            trusted_str = "\n".join(
                f"**{(role.name if (role := ctx.guild.get_role(int(rid))) else str(rid))}** → {', '.join(cogs)}"
                for rid, cogs in trusted_roles.items()
            )
        else:
            trusted_str = "None"

        embed = discord.Embed(
            title="Command Lockdown Status",
            color=(
                discord.Color.red() if guild_conf["lockdown"] else discord.Color.green()
            ),
        )
        embed.add_field(name="Lockdown", value=lockdown_status, inline=False)
        embed.add_field(name="Trusted Roles", value=trusted_str, inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CommandLockdown(bot))
