import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import List


class OwnerMaintenance(commands.Cog):
    """
    Global Owner Maintenance Mode (DM-safe)
    - Blocks all commands globally when active
    - Allows owner to whitelist users, roles, or servers for specific commands/cogs/all
    - Shows maintenance message lasting 5s, then deletes it
    - Owners can always manage from DMs even during maintenance
    """

    def __init__(self, bot: Red):
        self.bot: Red = bot
        self.config = Config.get_conf(
            self, identifier=8237482398, force_registration=True
        )
        self.config.register_global(
            maintenance_enabled=False,
            exceptions={},  # {id: {"type": "user"/"role"/"guild", "access": "all"/"cogs", "cogs": []}}
        )
        self.bot.add_check(self._maintenance_check)

    def cog_unload(self):
        try:
            self.bot.remove_check(self._maintenance_check)
        except Exception:
            pass

    async def _maintenance_check(self, ctx):
        """Global check applied to all commands."""
        # Always allow owners
        try:
            if await self.bot.is_owner(ctx.author):
                return True
        except Exception:
            pass

        # Always allow in DMs (for owner use)
        if ctx.guild is None:
            return True

        data = await self.config.all()
        if not data["maintenance_enabled"]:
            return True

        # Check allowlist exceptions
        exceptions = data["exceptions"]
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id)
        role_ids = {str(r.id) for r in getattr(ctx.author, "roles", [])}

        # Determine cog and command names
        cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
        cmd_name = ctx.command.qualified_name.lower() if ctx.command else None
        full_cmd = f"{cog_name}.{cmd_name}" if cog_name and cmd_name else None

        # Check exceptions
        for key, info in exceptions.items():
            if key not in {user_id, guild_id, *role_ids}:
                continue
            if info["access"] == "all":
                return True
            items = [i.lower() for i in info.get("cogs", [])]
            if cog_name in items or full_cmd in items:
                return True

        # If blocked, show maintenance message
        try:
            msg = await ctx.reply(
                "🛠️ The bot is currently under maintenance. Please try again later.",
                delete_after=5,
            )
        except discord.Forbidden:
            pass
        raise commands.CheckFailure("Bot is under maintenance")

    @commands.group(name="om", invoke_without_command=True)
    @checks.is_owner()
    async def om(self, ctx):
        """Owner Maintenance management commands."""
        await ctx.send_help()

    @om.command(name="toggle")
    @checks.is_owner()
    async def toggle(self, ctx):
        """Toggle global maintenance mode."""
        current = await self.config.maintenance_enabled()
        await self.config.maintenance_enabled.set(not current)
        await ctx.send(f"🛠️ Maintenance mode is now {'ON' if not current else 'OFF'}.")

    @om.command(name="set")
    @checks.is_owner()
    async def set(self, ctx, mode: str, target: str, *items: str):
        """
        Add or remove an exception.
        Usage: `d?om set <allow/deny> <user.id/mention/role.id/mention/server.id> <cog/cog.command/all>`
        """
        mode = mode.lower()
        if mode not in {"allow", "deny"}:
            return await ctx.send("❌ Mode must be `allow` or `deny`.")

        obj_type, obj_id = None, None

        # Detect object type and ID
        if target.isdigit():
            obj_id = int(target)
            # Guess type
            if ctx.guild and ctx.guild.get_member(obj_id):
                obj_type = "user"
            elif ctx.guild and ctx.guild.get_role(obj_id):
                obj_type = "role"
            elif self.bot.get_guild(obj_id):
                obj_type = "guild"
            else:
                obj_type = "unknown"
        elif target.startswith("<@") and target.endswith(">"):
            obj_type = "user"
            obj_id = int(target.strip("<@!>"))
        elif target.startswith("<@&") and target.endswith(">"):
            obj_type = "role"
            obj_id = int(target.strip("<@&>"))
        else:
            return await ctx.send("❌ Could not resolve target. Use ID or mention.")

        if not obj_id:
            return await ctx.send("❌ Invalid target provided.")

        data = await self.config.all()
        exceptions = data["exceptions"]
        key = str(obj_id)

        # Deny mode removes entry
        if mode == "deny":
            if key in exceptions:
                exceptions.pop(key)
                await self.config.exceptions.set(exceptions)
                return await ctx.send(
                    f"✅ Removed {obj_type} `{obj_id}` from allowlist."
                )
            else:
                return await ctx.send("❌ That target is not on the allowlist.")

        # Allow mode adds/updates entry
        if not items or items[0].lower() == "all":
            entry = {"type": obj_type, "access": "all", "cogs": []}
        else:
            entry = exceptions.get(
                key, {"type": obj_type, "access": "cogs", "cogs": []}
            )
            if entry["access"] != "all":
                entry["cogs"] = list(set(entry.get("cogs", [])) | set(items))
                entry["access"] = "cogs"

        exceptions[key] = entry
        await self.config.exceptions.set(exceptions)
        await ctx.send(
            f"✅ {obj_type.capitalize()} `{obj_id}` allowed for: {', '.join(items) if items else 'All'}"
        )

    @om.command(name="list")
    @checks.is_owner()
    async def list_exceptions(self, ctx):
        """List all global exceptions for maintenance mode."""
        data = await self.config.all()
        exceptions = data["exceptions"]

        if not exceptions:
            embed = discord.Embed(
                title="🛠️ Maintenance Exceptions",
                description="No exceptions set.",
                color=discord.Color.red(),
            )
            embed.set_footer(
                text=f"Maintenance Mode: {'ON' if data['maintenance_enabled'] else 'OFF'}"
            )
            return await ctx.send(embed=embed)

        lines = []
        for key, info in sorted(exceptions.items(), key=lambda x: x[0]):
            typ = info.get("type", "?").capitalize()
            access = info.get("access", "?")
            cogs = info.get("cogs", [])
            obj_str = f"{typ} {key}"
            if access == "all":
                lines.append(f"**{obj_str}** → ✅ All commands")
            else:
                lines.append(f"**{obj_str}** → {', '.join(cogs) if cogs else 'None'}")

        embed = discord.Embed(
            title="🛠️ Maintenance Mode Exceptions",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(
            text=f"Maintenance Mode: {'ON' if data['maintenance_enabled'] else 'OFF'}"
        )
        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(OwnerMaintenance(bot))
