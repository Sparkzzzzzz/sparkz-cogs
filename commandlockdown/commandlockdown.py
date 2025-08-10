from redbot.core import commands, Config
from redbot.core.bot import Red
import discord


class CommandLockdown(commands.Cog):
    """Restrict command usage during lockdown, with per-cog trust."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069, force_registration=True)
        self.config.register_guild(
            lockdown=False,
            trusted_roles_full=[],
            trusted_roles_cogs={},  # {role_id: [cog_names]}
        )

        bot.add_check(self.global_block_check)

    async def global_block_check(self, ctx: commands.Context):
        if ctx.guild is None:
            return True
        if await self.bot.is_owner(ctx.author):
            return True

        guild_conf = self.config.guild(ctx.guild)
        lockdown = await guild_conf.lockdown()
        if not lockdown:
            return True

        # Check trusted full-access roles
        trusted_full = await guild_conf.trusted_roles_full()
        if any(r.id in trusted_full for r in ctx.author.roles):
            return True

        # Check trusted per-cog roles
        trusted_cogs_map = await guild_conf.trusted_roles_cogs()
        cmd_cog = ctx.cog.__class__.__name__ if ctx.cog else None
        for role in ctx.author.roles:
            if str(role.id) in trusted_cogs_map:
                allowed_cogs = trusted_cogs_map[str(role.id)]
                if cmd_cog in allowed_cogs:
                    return True

        return False

    @commands.group(name="cl", aliases=["cmdlock"], invoke_without_command=True)
    @commands.guild_only()
    async def cl(self, ctx: commands.Context):
        """Manage command lockdown."""
        guild_conf = self.config.guild(ctx.guild)
        lockdown = await guild_conf.lockdown()
        trusted_full = await guild_conf.trusted_roles_full()
        trusted_cogs_map = await guild_conf.trusted_roles_cogs()

        embed = discord.Embed(
            title="🔒 Command Lockdown",
            description=f"**Status:** {'🟢 Enabled' if lockdown else '🔴 Disabled'}",
            color=discord.Color.red() if lockdown else discord.Color.green(),
        )

        if trusted_full:
            embed.add_field(
                name="Full Access Roles",
                value=", ".join(f"<@&{rid}>" for rid in trusted_full),
                inline=False,
            )

        if trusted_cogs_map:
            cog_lines = []
            for rid, cogs in trusted_cogs_map.items():
                cog_lines.append(f"<@&{rid}> → {', '.join(cogs)}")
            embed.add_field(
                name="Per-Cog Roles", value="\n".join(cog_lines), inline=False
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
    async def trust_role(
        self, ctx: commands.Context, role: discord.Role, *cogs_or_all: str
    ):
        """Trust a role with either full or per-cog access during lockdown.
        Example:
        - .cl trust @Mods all
        - .cl trust @Helpers Mod Cleanup
        """
        guild_conf = self.config.guild(ctx.guild)

        if not cogs_or_all:
            await ctx.send("❌ You must specify `all` or a list of cogs.")
            return

        if cogs_or_all[0].lower() == "all":
            trusted_full = await guild_conf.trusted_roles_full()
            if role.id not in trusted_full:
                trusted_full.append(role.id)
            await guild_conf.trusted_roles_full.set(trusted_full)

            trusted_cogs = await guild_conf.trusted_roles_cogs()
            trusted_cogs.pop(str(role.id), None)
            await guild_conf.trusted_roles_cogs.set(trusted_cogs)

            await ctx.send(
                f"✅ {role.mention} now has **full access** during lockdown."
            )
        else:
            trusted_cogs = await guild_conf.trusted_roles_cogs()
            trusted_cogs[str(role.id)] = list(cogs_or_all)
            await guild_conf.trusted_roles_cogs.set(trusted_cogs)

            trusted_full = await guild_conf.trusted_roles_full()
            if role.id in trusted_full:
                trusted_full.remove(role.id)
                await guild_conf.trusted_roles_full.set(trusted_full)

            await ctx.send(
                f"✅ {role.mention} now has access to: {', '.join(cogs_or_all)}."
            )

    @cl.command(name="untrust")
    @commands.has_guild_permissions(administrator=True)
    async def untrust_role(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from trusted lists."""
        guild_conf = self.config.guild(ctx.guild)
        trusted_full = await guild_conf.trusted_roles_full()
        trusted_cogs = await guild_conf.trusted_roles_cogs()

        removed = False

        if role.id in trusted_full:
            trusted_full.remove(role.id)
            await guild_conf.trusted_roles_full.set(trusted_full)
            removed = True

        if str(role.id) in trusted_cogs:
            trusted_cogs.pop(str(role.id))
            await guild_conf.trusted_roles_cogs.set(trusted_cogs)
            removed = True

        if removed:
            await ctx.send(f"✅ {role.mention} has been untrusted.")
        else:
            await ctx.send(f"ℹ️ {role.mention} was not trusted.")


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
