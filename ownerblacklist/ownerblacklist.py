import discord
from redbot.core import commands, checks, Config
from redbot.core.bot import Red
from typing import Optional, Dict


class OwnerBlacklist(commands.Cog):
    """Owner-only blacklist for specific users, cogs, commands, and servers."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=92384723984723, force_registration=True
        )
        self.config.register_global(blacklist={})
        bot.add_check(self._global_blacklist_check)

    def cog_unload(self):
        try:
            self.bot.remove_check(self._global_blacklist_check)
        except Exception:
            pass

    async def _global_blacklist_check(self, ctx: commands.Context) -> bool:
        """Silently check if a user is blacklisted before running any command."""
        bl_data: Dict = await self.config.blacklist()
        uid = str(ctx.author.id)
        if uid not in bl_data:
            return True

        # Check global "all" scope first
        if "all" in bl_data[uid]:
            entry = bl_data[uid]["all"]
            if entry.get("all", False):
                return False
            cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
            cmd_name = ctx.command.qualified_name.lower() if ctx.command else None
            full_cmd = f"{cog_name}.{cmd_name}" if cog_name and cmd_name else cmd_name
            if cog_name and cog_name in set(entry.get("cogs", [])):
                return False
            if full_cmd and full_cmd in set(entry.get("commands", [])):
                return False

        # Then check scope-specific
        scope_key = "dm" if ctx.guild is None else str(ctx.guild.id)
        if scope_key not in bl_data[uid]:
            return True

        entry = bl_data[uid][scope_key]

        if entry.get("all", False):
            return False

        cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
        cmd_name = ctx.command.qualified_name.lower() if ctx.command else None
        full_cmd = f"{cog_name}.{cmd_name}" if cog_name and cmd_name else cmd_name

        if cog_name and cog_name in set(entry.get("cogs", [])):
            return False
        if full_cmd and full_cmd in set(entry.get("commands", [])):
            return False

        return True

    def _format_scope_name(self, ctx, scope_key: str) -> str:
        """Return human-readable scope name."""
        if scope_key == "all":
            return "everywhere"
        elif scope_key == "dm":
            return "in DMs"
        elif scope_key == str(ctx.guild.id):
            return "in this server"
        else:
            guild = self.bot.get_guild(int(scope_key))
            return f"in server '{guild.name}'" if guild else f"in server ID {scope_key}"

    @commands.group(name="ownerblacklist", aliases=["ob"])
    @checks.is_owner()
    async def ob_group(self, ctx):
        """Manage Owner Blacklists."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @ob_group.command(name="add")
    @checks.is_owner()
    async def ob_add(
        self,
        ctx,
        user: discord.User,
        target: Optional[str] = "all",
        scope: Optional[str] = "guild",
    ):
        """Blacklist a user from a cog, command, or all."""
        bl_data = await self.config.blacklist()
        uid = str(user.id)
        if uid not in bl_data:
            bl_data[uid] = {}

        # Determine scope
        if scope.lower() == "all":
            scope_key = "all"
        elif scope.lower() == "dm":
            scope_key = "dm"
        elif scope.lower() == "guild":
            if ctx.guild is None:
                await ctx.send("❌ No guild context, specify a guild ID or use 'dm'.")
                return
            scope_key = str(ctx.guild.id)
        elif scope.isdigit():
            scope_key = scope
        else:
            await ctx.send("❌ Invalid scope. Use 'dm', 'guild', 'all', or a guild ID.")
            return

        if scope_key not in bl_data[uid]:
            bl_data[uid][scope_key] = {"all": False, "cogs": [], "commands": []}

        entry = bl_data[uid][scope_key]

        if target.lower() == "all":
            entry["all"] = True
            target_display = "all commands"
        elif "." in target:
            commands_set = set(entry.get("commands", []))
            commands_set.add(target.lower())
            entry["commands"] = list(commands_set)
            target_display = target
        else:
            cogs_set = set(entry.get("cogs", []))
            cogs_set.add(target.lower())
            entry["cogs"] = list(cogs_set)
            target_display = target

        bl_data[uid][scope_key] = entry
        await self.config.blacklist.set(bl_data)

        embed = discord.Embed(
            title="✅ Successfully Owner Blacklisted",
            description=f"{user.mention} from using `{target_display}` {self._format_scope_name(ctx, scope_key)}.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

    @ob_group.command(name="remove")
    @checks.is_owner()
    async def ob_remove(
        self,
        ctx,
        user: discord.User,
        target: Optional[str] = "all",
        scope: Optional[str] = "guild",
    ):
        """Remove a blacklist entry for a user."""
        bl_data = await self.config.blacklist()
        uid = str(user.id)
        if uid not in bl_data:
            await ctx.send(f"❌ {user} has no Owner Blacklist entries.")
            return

        if scope.lower() == "all":
            scope_key = "all"
        elif scope.lower() == "dm":
            scope_key = "dm"
        elif scope.lower() == "guild":
            if ctx.guild is None:
                await ctx.send("❌ No guild context, specify a guild ID or use 'dm'.")
                return
            scope_key = str(ctx.guild.id)
        elif scope.isdigit():
            scope_key = scope
        else:
            await ctx.send("❌ Invalid scope.")
            return

        if scope_key not in bl_data[uid]:
            await ctx.send(f"❌ {user} has no Owner Blacklist in that scope.")
            return

        entry = bl_data[uid][scope_key]
        if target.lower() == "all":
            entry["all"] = False
            target_display = "all commands"
        elif "." in target:
            commands_set = set(entry.get("commands", []))
            commands_set.discard(target.lower())
            entry["commands"] = list(commands_set)
            target_display = target
        else:
            cogs_set = set(entry.get("cogs", []))
            cogs_set.discard(target.lower())
            entry["cogs"] = list(cogs_set)
            target_display = target

        if not entry["all"] and not entry["cogs"] and not entry["commands"]:
            bl_data[uid].pop(scope_key)

        if not bl_data[uid]:
            bl_data.pop(uid)

        await self.config.blacklist.set(bl_data)

        embed = discord.Embed(
            title="✅ Successfully Removed from Owner Blacklist",
            description=f"{user.mention} — removed `{target_display}` {self._format_scope_name(ctx, scope_key)}.",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @ob_group.command(name="list")
    @checks.is_owner()
    async def ob_list(self, ctx, user: Optional[discord.User] = None):
        """List Owner Blacklist entries."""
        bl_data = await self.config.blacklist()
        if not bl_data:
            await ctx.send("✅ No Owner Blacklists set.")
            return

        if user:
            uid = str(user.id)
            if uid not in bl_data:
                await ctx.send(f"✅ {user} has no Owner Blacklist entries.")
                return
            data = bl_data[uid]
            lines = [f"Owner Blacklist for {user}:"]
            for scope, entry in data.items():
                scope_label = (
                    "Global"
                    if scope == "all"
                    else "DMs" if scope == "dm" else f"Guild {scope}"
                )
                lines.append(f"  Scope: {scope_label}")
                if entry["all"]:
                    lines.append("    ALL commands blocked")
                if entry["cogs"]:
                    lines.append(f"    Cogs: {', '.join(entry['cogs'])}")
                if entry["commands"]:
                    lines.append(f"    Commands: {', '.join(entry['commands'])}")
            await ctx.send("```" + "\n".join(lines) + "```")
        else:
            lines = ["All Owner Blacklists:"]
            for uid, scopes in bl_data.items():
                user_obj = self.bot.get_user(int(uid))
                uname = str(user_obj) if user_obj else uid
                lines.append(f"{uname}:")
                for scope, entry in scopes.items():
                    scope_label = (
                        "Global"
                        if scope == "all"
                        else "DMs" if scope == "dm" else f"Guild {scope}"
                    )
                    lines.append(f"  Scope: {scope_label}")
                    if entry["all"]:
                        lines.append("    ALL commands blocked")
                    if entry["cogs"]:
                        lines.append(f"    Cogs: {', '.join(entry['cogs'])}")
                    if entry["commands"]:
                        lines.append(f"    Commands: {', '.join(entry['commands'])}")
            await ctx.send("```" + "\n".join(lines) + "```")

    @ob_group.command(name="status")
    @checks.is_owner()
    async def ob_status(self, ctx):
        """Show all Owner Blacklists in an embed."""
        bl_data = await self.config.blacklist()
        embed = discord.Embed(
            title="Owner Blacklist Status",
            description="Current Owner Blacklist configuration",
            color=discord.Color.red(),
        )

        if not bl_data:
            embed.description = "✅ No Owner Blacklists set."
            await ctx.send(embed=embed)
            return

        for uid, scopes in bl_data.items():
            user_obj = self.bot.get_user(int(uid))
            uname = str(user_obj) if user_obj else f"[Unknown User {uid}]"
            value_lines = []
            for scope, entry in scopes.items():
                scope_title = (
                    "Global"
                    if scope == "all"
                    else "DMs" if scope == "dm" else f"Guild {scope}"
                )
                lines = [f"**Scope:** {scope_title}"]
                if entry["all"]:
                    lines.append("• ALL commands blocked")
                if entry["cogs"]:
                    lines.append(f"• Cogs: {', '.join(entry['cogs'])}")
                if entry["commands"]:
                    lines.append(f"• Commands: {', '.join(entry['commands'])}")
                value_lines.append("\n".join(lines))
            embed.add_field(name=uname, value="\n\n".join(value_lines), inline=False)

        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(OwnerBlacklist(bot))
