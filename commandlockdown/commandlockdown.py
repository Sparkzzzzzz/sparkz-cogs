import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red


class CommandLockdown(commands.Cog):
    """Lock down commands during emergencies, with role-based bypass."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=482947239472394, force_registration=True
        )

        default_guild = {
            "lockdown": False,
            "trusted_roles": [],  # full bypass
            "semi_trusted_roles": {},  # {role_id: [cog_names]}
        }
        self.config.register_guild(**default_guild)

    async def cog_check(self, ctx: commands.Context):
        """Global check to block commands when lockdown is active."""
        guild_conf = await self.config.guild(ctx.guild).all()
        if not guild_conf["lockdown"]:
            return True

        # Admins/bot owners always bypass
        if (
            await self.bot.is_owner(ctx.author)
            or ctx.author.guild_permissions.administrator
        ):
            return True

        author_roles = {r.id for r in ctx.author.roles}
        if any(rid in guild_conf["trusted_roles"] for rid in author_roles):
            return True

        # Semi-trust check
        for rid, allowed_cogs in guild_conf["semi_trusted_roles"].items():
            if (
                int(rid) in author_roles
                and ctx.cog
                and ctx.cog.qualified_name in allowed_cogs
            ):
                return True

        return False

    @commands.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def cl(self, ctx):
        """CommandLockdown management."""
        pass

    @cl.command()
    async def lockdown(self, ctx):
        """Enable lockdown mode."""
        await self.config.guild(ctx.guild).lockdown.set(True)
        await ctx.send("🔒 Lockdown enabled.")

    @cl.command()
    async def unlockdown(self, ctx):
        """Disable lockdown mode."""
        await self.config.guild(ctx.guild).lockdown.set(False)
        await ctx.send("🔓 Lockdown disabled.")

    @cl.command()
    async def trust(self, ctx, role: discord.Role, *cogs_or_all: str):
        """Trust a role for all cogs or specific cogs."""
        conf = await self.config.guild(ctx.guild).all()

        if len(cogs_or_all) == 1 and cogs_or_all[0].lower() == "all":
            if role.id not in conf["trusted_roles"]:
                conf["trusted_roles"].append(role.id)
            conf["semi_trusted_roles"].pop(str(role.id), None)
            await ctx.send(f"✅ {role.name} trusted for **all cogs**.")
        else:
            conf["semi_trusted_roles"][str(role.id)] = list(cogs_or_all)
            if role.id in conf["trusted_roles"]:
                conf["trusted_roles"].remove(role.id)
            await ctx.send(f"✅ {role.name} trusted for cogs: {', '.join(cogs_or_all)}")

        await self.config.guild(ctx.guild).set(conf)

    @cl.command()
    async def untrust(self, ctx, role: discord.Role):
        """Remove trust from a role."""
        conf = await self.config.guild(ctx.guild).all()
        if role.id in conf["trusted_roles"]:
            conf["trusted_roles"].remove(role.id)
        conf["semi_trusted_roles"].pop(str(role.id), None)
        await self.config.guild(ctx.guild).set(conf)
        await ctx.send(f"❌ Removed trust from {role.name}.")

    @cl.command()
    async def status(self, ctx):
        """Show lockdown status and trusted roles."""
        conf = await self.config.guild(ctx.guild).all()
        full_roles = [
            ctx.guild.get_role(rid).name
            for rid in conf["trusted_roles"]
            if ctx.guild.get_role(rid)
        ]
        semi_roles = [
            f"{ctx.guild.get_role(int(rid)).name}: {', '.join(cogs)}"
            for rid, cogs in conf["semi_trusted_roles"].items()
            if ctx.guild.get_role(int(rid))
        ]
        embed = discord.Embed(
            title="CommandLockdown Status",
            colour=discord.Colour.red() if conf["lockdown"] else discord.Colour.green(),
        )
        embed.add_field(
            name="Lockdown",
            value="Enabled" if conf["lockdown"] else "Disabled",
            inline=False,
        )
        embed.add_field(
            name="Full Trust",
            value=", ".join(full_roles) if full_roles else "None",
            inline=False,
        )
        embed.add_field(
            name="Semi Trust",
            value="\n".join(semi_roles) if semi_roles else "None",
            inline=False,
        )
        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
