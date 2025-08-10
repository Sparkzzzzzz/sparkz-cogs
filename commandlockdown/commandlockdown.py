import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import box


class CommandLockdown(commands.Cog):
    """Lock down bot commands to specific roles or cogs."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567890, force_registration=True
        )
        default_guild = {
            "locked": False,
            "trusted_roles": {},  # role_id: list of cogs or ["all"]
        }
        self.config.register_guild(**default_guild)

    async def cog_check(self, ctx):
        """Block commands when locked unless trusted."""
        locked = await self.config.guild(ctx.guild).locked()
        if not locked:
            return True
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        user_role_ids = {r.id for r in ctx.author.roles}
        for rid, cogs in trusted_roles.items():
            if int(rid) in user_role_ids:
                if "all" in cogs or ctx.cog.__class__.__name__ in cogs:
                    return True
        return False

    @commands.group(name="cl", invoke_without_command=True)
    @checks.admin_or_permissions(administrator=True)
    async def cl(self, ctx):
        """Command lockdown settings."""
        await ctx.send_help()

    @cl.command()
    @checks.admin_or_permissions(administrator=True)
    async def toggle(self, ctx):
        """Toggle command lockdown on/off."""
        current = await self.config.guild(ctx.guild).locked()
        await self.config.guild(ctx.guild).locked.set(not current)
        await ctx.send(f"🔒 Lockdown {'enabled' if not current else 'disabled'}.")

    @cl.command()
    @checks.admin_or_permissions(administrator=True)
    async def trust(self, ctx, role: discord.Role, *cogs):
        """Trust a role for specific cogs or 'all'."""
        trusted = await self.config.guild(ctx.guild).trusted_roles()
        role_id = str(role.id)
        trusted[role_id] = ["all"] if "all" in [c.lower() for c in cogs] else list(cogs)
        await self.config.guild(ctx.guild).trusted_roles.set(trusted)
        await ctx.send(f"✅ {role.name} trusted for: {', '.join(trusted[role_id])}")

    @cl.command()
    @checks.admin_or_permissions(administrator=True)
    async def untrust(self, ctx, role: discord.Role):
        """Remove a trusted role."""
        trusted = await self.config.guild(ctx.guild).trusted_roles()
        role_id = str(role.id)
        if role_id in trusted:
            del trusted[role_id]
            await self.config.guild(ctx.guild).trusted_roles.set(trusted)
            await ctx.send(f"❌ {role.name} untrusted.")
        else:
            await ctx.send("That role isn't trusted.")

    @cl.command()
    async def status(self, ctx):
        """Show lockdown status and trusted roles."""
        locked = await self.config.guild(ctx.guild).locked()
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        embed = discord.Embed(
            title="Command Lockdown Status",
            color=discord.Color.red() if locked else discord.Color.green(),
        )
        embed.add_field(
            name="Lockdown",
            value="🔒 Enabled" if locked else "🔓 Disabled",
            inline=False,
        )
        if trusted_roles:
            role_list = []
            for rid, cogs in trusted_roles.items():
                role_obj = ctx.guild.get_role(int(rid))
                if role_obj:
                    role_list.append(f"**{role_obj.name}** → {', '.join(cogs)}")
            embed.add_field(
                name="Trusted Roles", value="\n".join(role_list), inline=False
            )
        else:
            embed.add_field(name="Trusted Roles", value="None", inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CommandLockdown(bot))
