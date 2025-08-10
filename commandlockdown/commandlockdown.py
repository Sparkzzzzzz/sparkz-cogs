import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import Optional


class CommandLockdown(commands.Cog):
    """Lock down commands and cogs to trusted roles during lockdown."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "lockdown": False,
            "trusted_roles": {},  # role_id: [cog1, cog2, ...]
        }
        self.config.register_guild(**default_guild)

    async def cog_check(self, ctx: commands.Context):
        """Only allow owners to use .cl commands."""
        if ctx.command.qualified_name.startswith("cl"):
            return ctx.author.id in self.bot.owner_ids
        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        """Enforce lockdown restrictions before any command."""
        if ctx.command.qualified_name.startswith("cl"):
            return  # Let owner bypass here — handled in cog_check

        guild_conf = await self.config.guild(ctx.guild).all()

        if guild_conf["lockdown"]:
            # Owner bypass
            if ctx.author.id in self.bot.owner_ids:
                return

            trusted_roles = guild_conf["trusted_roles"]
            user_role_ids = {r.id for r in ctx.author.roles}

            allowed_cogs = set()
            for rid, cogs in trusted_roles.items():
                if int(rid) in user_role_ids:
                    allowed_cogs.update(c.lower() for c in cogs)

            if ctx.cog and ctx.cog.qualified_name.lower() in allowed_cogs:
                return  # Allow this command

            raise commands.CheckFailure(
                "🚫 Lockdown in effect. You are not allowed to use this command."
            )

    @commands.group()
    async def cl(self, ctx: commands.Context):
        """Command Lockdown configuration."""
        pass

    @cl.command()
    async def toggle(self, ctx: commands.Context):
        """Toggle lockdown mode on or off."""
        current = await self.config.guild(ctx.guild).lockdown()
        await self.config.guild(ctx.guild).lockdown.set(not current)
        status = "ON 🔒" if not current else "OFF 🔓"
        await ctx.send(f"✅ Lockdown is now **{status}**")

    @cl.command()
    async def trust(self, ctx: commands.Context, role: discord.Role, *cogs: str):
        """Trust a role for specific cogs (use 'all' for all cogs)."""
        role_id = str(role.id)
        guild_conf = await self.config.guild(ctx.guild).trusted_roles()

        if cogs and cogs[0].lower() == "all":
            all_cogs = [c.qualified_name for c in self.bot.cogs.values()]
            guild_conf[role_id] = all_cogs
        else:
            guild_conf[role_id] = list(cogs)

        await self.config.guild(ctx.guild).trusted_roles.set(guild_conf)
        await ctx.send(
            f"✅ Trusted role **{role.name}** for: {', '.join(guild_conf[role_id])}"
        )

    @cl.command()
    async def untrust(self, ctx: commands.Context, role: discord.Role):
        """Remove a trusted role."""
        role_id = str(role.id)
        guild_conf = await self.config.guild(ctx.guild).trusted_roles()
        if role_id in guild_conf:
            del guild_conf[role_id]
            await self.config.guild(ctx.guild).trusted_roles.set(guild_conf)
            await ctx.send(f"✅ Removed trust for **{role.name}**")
        else:
            await ctx.send("❌ That role is not trusted.")

    @cl.command()
    async def status(self, ctx: commands.Context):
        """Show lockdown status and trusted roles."""
        guild_conf = await self.config.guild(ctx.guild).all()
        lockdown_status = "🔒 **ON**" if guild_conf["lockdown"] else "🔓 **OFF**"

        trusted_info = []
        for rid, cogs in guild_conf["trusted_roles"].items():
            role = ctx.guild.get_role(int(rid))
            role_name = role.name if role else f"(deleted role {rid})"
            trusted_info.append(f"**{role_name}** → {', '.join(cogs)}")

        embed = discord.Embed(
            title="Command Lockdown Status",
            description=f"Lockdown: {lockdown_status}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Trusted Roles",
            value="\n".join(trusted_info) if trusted_info else "None",
        )
        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
