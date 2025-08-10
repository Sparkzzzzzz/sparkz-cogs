from redbot.core import commands, Config
from redbot.core.bot import Red
import discord


class CommandLockdown(commands.Cog):
    """Lock down commands server-wide, with per-role and per-cog trust."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=42069, force_registration=True)
        self.config.register_guild(
            lockdown=False,
            trusted_roles={},  # {role_id: {"all": bool, "cogs": [str, ...]}}
        )

        bot.add_check(self.global_block_check)

    async def global_block_check(self, ctx: commands.Context):
        if ctx.guild is None:
            return True
        if await self.bot.is_owner(ctx.author):
            return True

        lockdown = await self.config.guild(ctx.guild).lockdown()
        if not lockdown:
            return True

        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()
        user_role_ids = {r.id for r in ctx.author.roles}

        # Check if any of the user's roles bypass lockdown
        for rid, trust_data in trusted_roles.items():
            if int(rid) in user_role_ids:
                if trust_data.get("all", False):
                    return True
                if ctx.command.cog_name in trust_data.get("cogs", []):
                    return True

        return False

    @commands.group(name="cl", aliases=["cmdlock"], invoke_without_command=True)
    @commands.guild_only()
    async def cl(self, ctx: commands.Context):
        """Manage command lockdown."""
        lockdown = await self.config.guild(ctx.guild).lockdown()
        trusted_roles = await self.config.guild(ctx.guild).trusted_roles()

        desc_lines = []
        for rid, trust_data in trusted_roles.items():
            role_mention = f"<@&{rid}>"
            if trust_data.get("all", False):
                desc_lines.append(f"{role_mention}: **All Cogs**")
            else:
                cogs = trust_data.get("cogs", [])
                desc_lines.append(
                    f"{role_mention}: {', '.join(cogs) if cogs else 'None'}"
                )

        embed = discord.Embed(
            title="🔒 Command Lockdown",
            description=(
                f"**Status:** {'🟢 Enabled' if lockdown else '🔴 Disabled'}\n"
                f"**Trusted Roles:**\n{chr(10).join(desc_lines) if desc_lines else 'None'}"
            ),
            color=discord.Color.red() if lockdown else discord.Color.green(),
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
        """Trust a role for all or specific cogs.
        Usage:
          - .cl trust @Role all
          - .cl trust @Role Audio Moderation
        """
        trusted = await self.config.guild(ctx.guild).trusted_roles()
        rid = str(role.id)

        if not cogs_or_all:
            return await ctx.send("You must specify `all` or one or more cog names.")

        if rid not in trusted:
            trusted[rid] = {"all": False, "cogs": []}

        if len(cogs_or_all) == 1 and cogs_or_all[0].lower() == "all":
            trusted[rid]["all"] = True
            trusted[rid]["cogs"] = []
            await ctx.send(f"{role.mention} is now trusted for **all cogs**.")
        else:
            trusted[rid]["all"] = False
            trusted[rid]["cogs"] = list(
                set(trusted[rid].get("cogs", []) + list(cogs_or_all))
            )
            await ctx.send(
                f"{role.mention} is now trusted for: {', '.join(trusted[rid]['cogs'])}"
            )

        await self.config.guild(ctx.guild).trusted_roles.set(trusted)

    @cl.command(name="untrust")
    @commands.has_guild_permissions(administrator=True)
    async def untrust_role(
        self, ctx: commands.Context, role: discord.Role, *cogs_or_all: str
    ):
        """Remove trust from a role for all or specific cogs.
        Usage:
          - .cl untrust @Role all
          - .cl untrust @Role Audio Moderation
        """
        trusted = await self.config.guild(ctx.guild).trusted_roles()
        rid = str(role.id)

        if rid not in trusted:
            return await ctx.send(f"{role.mention} is not trusted for anything.")

        if not cogs_or_all:
            return await ctx.send("You must specify `all` or one or more cog names.")

        if len(cogs_or_all) == 1 and cogs_or_all[0].lower() == "all":
            trusted.pop(rid)
            await ctx.send(f"{role.mention} is no longer trusted at all.")
        else:
            current_cogs = set(trusted[rid].get("cogs", []))
            updated_cogs = current_cogs - set(cogs_or_all)
            trusted[rid]["cogs"] = list(updated_cogs)

            # If no cogs left and not trusted for all, remove entry
            if not updated_cogs and not trusted[rid].get("all", False):
                trusted.pop(rid)
                await ctx.send(f"{role.mention} is no longer trusted for any cogs.")
            else:
                await ctx.send(
                    f"{role.mention} is now trusted for: {', '.join(updated_cogs) if updated_cogs else 'None'}"
                )

        await self.config.guild(ctx.guild).trusted_roles.set(trusted)
