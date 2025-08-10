import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import box
from typing import List


class CommandLockdown(commands.Cog):
    """Lock down specific cogs to certain roles."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9876543210)
        default_guild = {
            "lockdown": False,
            "trusted_roles": [],
            "semi_trusted_roles": {},  # {role_id: [cog_names]}
        }
        self.config.register_guild(**default_guild)

    async def cog_check(self, ctx):
        # Always allow owner to run everything
        if await self.bot.is_owner(ctx.author):
            return True

        # Special case: `.cl` commands are *always* owner-only
        if ctx.command and ctx.command.qualified_name.startswith("cl"):
            return False

        lockdown = await self.config.guild(ctx.guild).lockdown()
        if not lockdown:
            return True

        trusted = await self.config.guild(ctx.guild).trusted_roles()
        semi_trusted = await self.config.guild(ctx.guild).semi_trusted_roles()

        # Full trust check
        if any(r.id in trusted for r in ctx.author.roles):
            return True

        # Semi-trust check for cog-specific access
        for role in ctx.author.roles:
            if str(role.id) in semi_trusted:
                allowed_cogs = semi_trusted[str(role.id)]
                if ctx.cog and ctx.cog.qualified_name in allowed_cogs:
                    return True
        return False

    @commands.group()
    @checks.is_owner()
    async def cl(self, ctx):
        """Command lockdown settings."""
        pass

    @cl.command()
    async def toggle(self, ctx):
        """Toggle lockdown on/off."""
        guild_conf = self.config.guild(ctx.guild)
        state = not (await guild_conf.lockdown())
        await guild_conf.lockdown.set(state)
        await ctx.send(f"🔒 Lockdown {'enabled' if state else 'disabled'}.")

    @cl.command()
    async def status(self, ctx):
        """Show lockdown status and role access."""
        lockdown = await self.config.guild(ctx.guild).lockdown()
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        semi_trusted = await self.config.guild(ctx.guild).semi_trusted_roles()

        trusted_mentions = [
            ctx.guild.get_role(r).mention
            for r in trusted_roles
            if ctx.guild.get_role(r)
        ]
        semi_trusted_display = []
        for role_id, cogs in semi_trusted.items():
            role = ctx.guild.get_role(int(role_id))
            if role:
                semi_trusted_display.append(f"{role.mention}: {', '.join(cogs)}")

        embed = discord.Embed(
            title="Command Lockdown Status", color=discord.Color.blurple()
        )
        embed.add_field(
            name="Lockdown Active",
            value="✅ Yes" if lockdown else "❌ No",
            inline=False,
        )
        embed.add_field(
            name="Trusted Roles (Full Access)",
            value=", ".join(trusted_mentions) or "None",
            inline=False,
        )
        embed.add_field(
            name="Semi-Trusted Roles (Cog-Specific)",
            value="\n".join(semi_trusted_display) or "None",
            inline=False,
        )

        await ctx.send(embed=embed)

    @cl.command()
    async def trust(self, ctx, role: discord.Role, *cogs: str):
        """Trust a role fully or for specific cogs."""
        if not cogs or cogs[0].lower() == "all":
            async with self.config.guild(ctx.guild).trusted_roles() as trusted:
                if role.id not in trusted:
                    trusted.append(role.id)
            await ctx.send(
                f"✅ {role.mention} now has **full access** during lockdown."
            )
        else:
            async with self.config.guild(
                ctx.guild
            ).semi_trusted_roles() as semi_trusted:
                semi_trusted[str(role.id)] = list(cogs)
            await ctx.send(
                f"✅ {role.mention} now has **access to cogs:** {', '.join(cogs)} during lockdown."
            )

    @cl.command()
    async def untrust(self, ctx, role: discord.Role):
        """Remove a role's trust."""
        async with self.config.guild(ctx.guild).trusted_roles() as trusted:
            if role.id in trusted:
                trusted.remove(role.id)
        async with self.config.guild(ctx.guild).semi_trusted_roles() as semi_trusted:
            semi_trusted.pop(str(role.id), None)
        await ctx.send(
            f"❌ {role.mention} no longer has special access during lockdown."
        )
