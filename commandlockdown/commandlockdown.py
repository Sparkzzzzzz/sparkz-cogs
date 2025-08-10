import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red


class CommandLockdown(commands.Cog):
    """Lock down command usage to certain roles per cog."""

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {"lockdown": False, "trusted_roles": {}}  # role_id: [cog_names]
        self.config.register_guild(**default_guild)
        bot.add_check(self.global_lockdown_check)  # ✅ enforce lockdown globally

    async def global_lockdown_check(self, ctx: commands.Context):
        """Global lockdown check for all commands."""
        # Always allow owners
        if ctx.author.id in self.bot.owner_ids:
            return True

        # Ignore DMs
        if not ctx.guild:
            return True

        guild_conf = await self.config.guild(ctx.guild).all()
        if not guild_conf["lockdown"]:
            return True

        trusted_roles = guild_conf["trusted_roles"]
        user_role_ids = {r.id for r in ctx.author.roles}
        allowed_cogs = set()

        for rid, cogs in trusted_roles.items():
            if int(rid) in user_role_ids:
                allowed_cogs.update(c.lower() for c in cogs)

        if ctx.cog and ctx.cog.qualified_name.lower() in allowed_cogs:
            return True

        raise commands.CheckFailure(
            "🚫 Lockdown is active. You are not allowed to use this command."
        )

    @commands.group(name="cl", invoke_without_command=True)
    @checks.is_owner()
    async def cl_group(self, ctx):
        """Manage Command Lockdown."""
        await ctx.send_help()

    @cl_group.command(name="toggle")
    @checks.is_owner()
    async def cl_toggle(self, ctx):
        """Toggle lockdown mode."""
        guild_conf = await self.config.guild(ctx.guild).all()
        new_state = not guild_conf["lockdown"]
        await self.config.guild(ctx.guild).lockdown.set(new_state)
        await ctx.send(f"🔒 Lockdown {'enabled' if new_state else 'disabled'}.")

    @cl_group.command(name="trust")
    @checks.is_owner()
    async def cl_trust(self, ctx, role: discord.Role, *cogs: str):
        """Trust a role for specific cogs."""
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        trusted_roles[str(role.id)] = list(cogs)
        await self.config.guild(ctx.guild).trusted_roles.set(trusted_roles)
        await ctx.send(
            f"✅ Trusted **{role.name}** for cogs: {', '.join(cogs) if cogs else 'All'}"
        )

    @cl_group.command(name="status")
    @checks.is_owner()
    async def cl_status(self, ctx):
        """Show current lockdown status."""
        guild_conf = await self.config.guild(ctx.guild).all()
        embed = discord.Embed(
            title="Command Lockdown Status",
            color=(
                discord.Color.red() if guild_conf["lockdown"] else discord.Color.green()
            ),
        )
        embed.add_field(name="Lockdown Active", value=str(guild_conf["lockdown"]))
        if guild_conf["trusted_roles"]:
            role_lines = []
            for rid, cogs in guild_conf["trusted_roles"].items():
                role_obj = ctx.guild.get_role(int(rid))
                role_name = role_obj.name if role_obj else f"Unknown Role ({rid})"
                role_lines.append(
                    f"**{role_name}** → {', '.join(cogs) if cogs else 'All'}"
                )
            embed.add_field(
                name="Trusted Roles", value="\n".join(role_lines), inline=False
            )
        else:
            embed.add_field(name="Trusted Roles", value="None")
        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
