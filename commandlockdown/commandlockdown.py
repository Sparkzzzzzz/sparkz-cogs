import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from discord.ext import commands as dcommands


class CommandLockdown(commands.Cog):
    """Lock commands during lockdown except for trusted roles."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=84738293048, force_registration=True
        )
        self.config.register_guild(
            lockdown_enabled=False,
            trusted_roles={},  # role_id: {"access": "all" or "cogs", "cogs": [list]}
        )
        bot.add_check(self.global_lockdown_check)

    async def global_lockdown_check(self, ctx: commands.Context):
        """Global check for lockdown."""
        guild = ctx.guild
        if not guild:
            return True

        data = await self.config.guild(guild).all()
        lockdown_enabled = data["lockdown_enabled"]

        # If lockdown is off
        if not lockdown_enabled:
            return True

        # Owner always allowed
        if await self.bot.is_owner(ctx.author):
            return True

        trusted_roles = data["trusted_roles"]

        # Check if user has any trusted role
        for role in ctx.author.roles:
            role_data = trusted_roles.get(str(role.id))
            if role_data:
                if role_data["access"] == "all":
                    return True
                elif role_data["access"] == "cogs":
                    if ctx.command.cog_name in role_data["cogs"]:
                        return True
        return False

    async def _find_role(self, ctx: commands.Context, role_input: str):
        """Find role by ID, mention, or name."""
        role_id = None
        if role_input.isdigit():
            role_id = int(role_input)
        elif role_input.startswith("<@&") and role_input.endswith(">"):
            role_id = int(role_input[3:-1])
        else:
            role = discord.utils.find(
                lambda r: r.name.lower() == role_input.lower(), ctx.guild.roles
            )
            if role:
                return role

        if role_id:
            return ctx.guild.get_role(role_id)
        return None

    @commands.group(name="cl")
    @checks.admin_or_permissions(manage_guild=True)
    async def cl_group(self, ctx: commands.Context):
        """Command lockdown management."""
        pass

    @cl_group.command(name="toggle")
    async def cl_toggle(self, ctx: commands.Context):
        """Toggle lockdown on/off."""
        current = await self.config.guild(ctx.guild).lockdown_enabled()
        await self.config.guild(ctx.guild).lockdown_enabled.set(not current)
        await ctx.send(f"🔒 Lockdown mode {'enabled' if not current else 'disabled'}.")

    @cl_group.command(name="trust")
    async def cl_trust(self, ctx: commands.Context, role_input: str, *cogs):
        """Trust a role for all commands or specific cogs."""
        role = await self._find_role(ctx, role_input)
        if not role:
            await ctx.send("Role not found.")
            return

        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        if len(cogs) == 1 and cogs[0].lower() == "all":
            trusted_roles[str(role.id)] = {"access": "all", "cogs": []}
        else:
            trusted_roles[str(role.id)] = {"access": "cogs", "cogs": list(cogs)}

        await self.config.guild(ctx.guild).trusted_roles.set(trusted_roles)
        await ctx.send(
            f"Trusted role `{role.name}` for {'all commands' if cogs and cogs[0].lower() == 'all' else ', '.join(cogs)}."
        )

    @cl_group.command(name="untrust")
    async def cl_untrust(self, ctx: commands.Context, role_input: str):
        """Remove a role from trusted roles."""
        role = await self._find_role(ctx, role_input)
        role_id = None
        if role:
            role_id = str(role.id)
        elif role_input.isdigit():
            role_id = role_input

        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        if role_id in trusted_roles:
            del trusted_roles[role_id]
            await self.config.guild(ctx.guild).trusted_roles.set(trusted_roles)
            await ctx.send(
                f"Role `{role.name if role else role_id}` is no longer trusted."
            )
        else:
            await ctx.send("That role is not trusted.")

    @cl_group.command(name="status")
    async def cl_status(self, ctx: commands.Context):
        """Show lockdown status and trusted roles."""
        data = await self.config.guild(ctx.guild).all()
        lockdown_enabled = data["lockdown_enabled"]
        trusted_roles = data["trusted_roles"]

        desc = f"**Lockdown Enabled**: {'✅ Yes' if lockdown_enabled else '❌ No'}\n\n"
        desc += "**Trusted Roles:**\n"
        if not trusted_roles:
            desc += "None"
        else:
            for role_id, info in trusted_roles.items():
                role_obj = ctx.guild.get_role(int(role_id))
                role_name = role_obj.name if role_obj else f"[Unknown Role {role_id}]"
                if info["access"] == "all":
                    desc += f"{role_name} → All commands\n"
                else:
                    desc += f"{role_name} → {', '.join(info['cogs'])}\n"

        embed = discord.Embed(
            title="Command Lockdown Status",
            description=desc,
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
