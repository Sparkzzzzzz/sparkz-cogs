import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box


class CommandLockdown(commands.Cog):
    """Lock down commands to certain roles during lockdown."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567890, force_registration=True
        )
        default_guild = {
            "lockdown": False,
            "trusted_roles": {},  # role_id: [cog_names]
        }
        self.config.register_guild(**default_guild)

    # --------------------
    # INTERNAL CHECK
    # --------------------
    async def cog_check(self, ctx: commands.Context):
        """Global check for lockdown."""
        if await self.bot.is_owner(ctx.author):
            return True  # Owner always bypasses
        guild_conf = await self.config.guild(ctx.guild).all()
        if not guild_conf["lockdown"]:
            return True  # Lockdown off
        trusted_roles = guild_conf["trusted_roles"]
        if not trusted_roles:
            return False
        author_roles = {r.id for r in ctx.author.roles}
        for role_id, cogs in trusted_roles.items():
            if role_id in author_roles:
                if "all" in cogs or ctx.cog.__class__.__name__ in cogs:
                    return True
        return False

    # --------------------
    # COMMAND GROUP
    # --------------------
    @commands.group(name="cl")
    @checks.is_owner()
    async def cl_group(self, ctx):
        """Manage Command Lockdown."""
        pass

    @cl_group.command(name="toggle")
    async def cl_toggle(self, ctx):
        """Toggle lockdown on/off."""
        current = await self.config.guild(ctx.guild).lockdown()
        await self.config.guild(ctx.guild).lockdown.set(not current)
        await ctx.send(f"🔒 Lockdown is now {'ON' if not current else 'OFF'}.")

    @cl_group.command(name="trust")
    async def cl_trust(self, ctx, role: discord.Role, *cogs: str):
        """Trust a role for specific cogs or all."""
        guild_conf = await self.config.guild(ctx.guild).trusted_roles()
        role_id = role.id
        if role_id not in guild_conf:
            guild_conf[role_id] = []
        if not cogs:
            cogs = ["all"]
        guild_conf[role_id] = list(set(guild_conf[role_id]) | set(cogs))
        await self.config.guild(ctx.guild).trusted_roles.set(guild_conf)
        await ctx.send(f"✅ Role **{role.name}** is now trusted for: {', '.join(cogs)}")

    @cl_group.command(name="untrust")
    async def cl_untrust(self, ctx, role: discord.Role):
        """Remove a role from trusted list."""
        guild_conf = await self.config.guild(ctx.guild).trusted_roles()
        if role.id in guild_conf:
            del guild_conf[role.id]
            await self.config.guild(ctx.guild).trusted_roles.set(guild_conf)
            await ctx.send(f"❌ Role **{role.name}** is no longer trusted.")
        else:
            await ctx.send(f"ℹ️ Role **{role.name}** is not trusted.")

    @cl_group.command(name="status")
    async def cl_status(self, ctx):
        """Show lockdown status and trusted roles."""
        guild_conf = await self.config.guild(ctx.guild).all()
        lockdown_status = "ON 🔒" if guild_conf["lockdown"] else "OFF 🔓"
        trusted_roles = guild_conf["trusted_roles"]
        if trusted_roles:
            trusted_str = "\n".join(
                f"**{ctx.guild.get_role(rid).name if ctx.guild.get_role(rid) else rid}** → {', '.join(cogs)}"
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

    # --------------------
    # QUIET IGNORE
    # --------------------
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            return  # silently ignore
