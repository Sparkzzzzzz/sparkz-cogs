import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import Optional, Dict, Any, List


class CommandLockdown(commands.Cog):
    """
    CommandLockdown with:
    - Role/User allow lists (full, cog-level, command-level)
    - Role/User deny lists (cog-level, command-level)
    - Deny always overrides allow
    """

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot
        self.config: Config = Config.get_conf(
            self, identifier=84738293048, force_registration=True
        )
        self.config.register_guild(
            lockdown_enabled=False,
            trusted_roles={},  # role_id -> {"access": "all"|"cogs", "cogs": [...]}
            trusted_users={},  # user_id -> {"access": "all"|"cogs", "cogs": [...]}
            denied_roles={},  # role_id -> {"cogs": [...]}
            denied_users={},  # user_id -> {"cogs": [...]}
        )

        self._original_checks: List = []
        try:
            existing = list(getattr(self.bot, "_checks", []))
        except Exception:
            existing = []

        for chk in existing:
            try:
                self.bot.remove_check(chk)
                self._original_checks.append(chk)
            except Exception:
                pass

        self.bot.add_check(self._global_lockdown_check)

    def cog_unload(self) -> None:
        try:
            self.bot.remove_check(self._global_lockdown_check)
        except Exception:
            pass
        for chk in self._original_checks:
            try:
                self.bot.add_check(chk)
            except Exception:
                pass

    async def _resolve_role(
        self, ctx: commands.Context, role_input: str
    ) -> Optional[discord.Role]:
        if role_input.startswith("<@&") and role_input.endswith(">"):
            inner = role_input[3:-1]
            if inner.isdigit():
                return ctx.guild.get_role(int(inner))
        if role_input.isdigit():
            r = ctx.guild.get_role(int(role_input))
            if r:
                return r
        name = role_input.strip()
        for r in ctx.guild.roles:
            if r.name.lower() == name.lower():
                return r
        return None

    async def _resolve_member(
        self, ctx: commands.Context, member_input: str
    ) -> Optional[discord.Member]:
        if member_input.startswith("<@") and member_input.endswith(">"):
            inner = member_input.strip("<@!>")
            if inner.isdigit():
                return ctx.guild.get_member(int(inner))
        if member_input.isdigit():
            return ctx.guild.get_member(int(member_input))
        name = member_input.strip().lower()
        for m in ctx.guild.members:
            if m.name.lower() == name or f"{m.name.lower()}#{m.discriminator}" == name:
                return m
        return None

    async def _is_match(self, items: List[str], ctx: commands.Context) -> bool:
        cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
        cmd_name = ctx.command.qualified_name.lower() if ctx.command else None
        full_cmd = f"{cog_name}.{cmd_name}" if cog_name and cmd_name else None
        items_lower = {i.lower() for i in items}
        if cog_name and cog_name in items_lower:
            return True
        if full_cmd and full_cmd in items_lower:
            return True
        return False

    async def _global_lockdown_check(self, ctx: commands.Context) -> bool:
        try:
            if await self.bot.is_owner(ctx.author):
                return True
        except Exception:
            if hasattr(self.bot, "owner_ids") and ctx.author.id in getattr(
                self.bot, "owner_ids", set()
            ):
                return True
        if ctx.guild is None:
            return True

        data = await self.config.guild(ctx.guild).all()
        if not data.get("lockdown_enabled", False):
            return True

        trusted_roles = data.get("trusted_roles", {}) or {}
        trusted_users = data.get("trusted_users", {}) or {}
        denied_roles = data.get("denied_roles", {}) or {}
        denied_users = data.get("denied_users", {}) or {}
        user_role_ids = {str(r.id) for r in ctx.author.roles}

        # 1. DENY LISTS CHECK (override allow)
        # User-level deny
        if str(ctx.author.id) in denied_users:
            if await self._is_match(
                denied_users[str(ctx.author.id)].get("cogs", []), ctx
            ):
                return False
        # Role-level deny
        for rid, info in denied_roles.items():
            if rid in user_role_ids and await self._is_match(info.get("cogs", []), ctx):
                return False

        # 2. ALLOW LISTS CHECK
        # User-level allow
        if str(ctx.author.id) in trusted_users:
            info = trusted_users[str(ctx.author.id)]
            if info.get("access") == "all":
                return True
            if await self._is_match(info.get("cogs", []), ctx):
                return True

        # Role-level allow
        allowed_items = set()
        allow_all = False
        for rid, info in trusted_roles.items():
            if rid in user_role_ids:
                if info.get("access") == "all":
                    allow_all = True
                    break
                allowed_items.update(info.get("cogs", []))
        if allow_all:
            return True
        if await self._is_match(list(allowed_items), ctx):
            return True

        return False

    @commands.group(name="cl", invoke_without_command=True)
    @checks.is_owner()
    async def cl(self, ctx: commands.Context):
        await ctx.send_help()

    # ===== ALLOW COMMANDS =====

    @cl.command(name="trust")
    @checks.is_owner()
    async def cl_trust(self, ctx: commands.Context, role_input: str, *items: str):
        role = await self._resolve_role(ctx, role_input)
        if not role:
            return await ctx.send("❌ Role not found.")
        trusted = await self.config.guild(ctx.guild).trusted_roles()
        if len(items) == 0 or (len(items) == 1 and items[0].lower() == "all"):
            trusted[str(role.id)] = {"access": "all", "cogs": []}
        else:
            trusted[str(role.id)] = {"access": "cogs", "cogs": list(items)}
        await self.config.guild(ctx.guild).trusted_roles.set(trusted)
        await ctx.send(
            f"✅ Role **{role.name}** trusted for: {'All' if trusted[str(role.id)]['access']=='all' else ', '.join(trusted[str(role.id)]['cogs'])}"
        )

    @cl.command(name="allowuser")
    @checks.is_owner()
    async def cl_allowuser(self, ctx: commands.Context, member_input: str, *items: str):
        member = await self._resolve_member(ctx, member_input)
        if not member:
            return await ctx.send("❌ User not found.")
        trusted = await self.config.guild(ctx.guild).trusted_users()
        if len(items) == 0 or (len(items) == 1 and items[0].lower() == "all"):
            trusted[str(member.id)] = {"access": "all", "cogs": []}
        else:
            trusted[str(member.id)] = {"access": "cogs", "cogs": list(items)}
        await self.config.guild(ctx.guild).trusted_users.set(trusted)
        await ctx.send(
            f"✅ User **{member}** trusted for: {'All' if trusted[str(member.id)]['access']=='all' else ', '.join(trusted[str(member.id)]['cogs'])}"
        )

    # ===== DENY COMMANDS =====

    @cl.command(name="denyrole")
    @checks.is_owner()
    async def cl_denyrole(self, ctx: commands.Context, role_input: str, *items: str):
        role = await self._resolve_role(ctx, role_input)
        if not role:
            return await ctx.send("❌ Role not found.")
        denied = await self.config.guild(ctx.guild).denied_roles()
        current = set(denied.get(str(role.id), {}).get("cogs", []))
        current.update(items)
        denied[str(role.id)] = {"cogs": list(current)}
        await self.config.guild(ctx.guild).denied_roles.set(denied)
        await ctx.send(f"⛔ Role **{role.name}** denied for: {', '.join(items)}")

    @cl.command(name="denyuser")
    @checks.is_owner()
    async def cl_denyuser(self, ctx: commands.Context, member_input: str, *items: str):
        member = await self._resolve_member(ctx, member_input)
        if not member:
            return await ctx.send("❌ User not found.")
        denied = await self.config.guild(ctx.guild).denied_users()
        current = set(denied.get(str(member.id), {}).get("cogs", []))
        current.update(items)
        denied[str(member.id)] = {"cogs": list(current)}
        await self.config.guild(ctx.guild).denied_users.set(denied)
        await ctx.send(f"⛔ User **{member}** denied for: {', '.join(items)}")

    # ===== REMOVE DENY COMMANDS =====

    @cl.command(name="undenyrole")
    @checks.is_owner()
    async def cl_undenyrole(self, ctx: commands.Context, role_input: str, *items: str):
        role = await self._resolve_role(ctx, role_input)
        if not role:
            return await ctx.send("❌ Role not found.")
        denied = await self.config.guild(ctx.guild).denied_roles()
        if str(role.id) not in denied:
            return await ctx.send("⚠️ Role has no denies.")
        current = set(denied[str(role.id)]["cogs"])
        current.difference_update(items)
        denied[str(role.id)]["cogs"] = list(current)
        await self.config.guild(ctx.guild).denied_roles.set(denied)
        await ctx.send(f"✅ Removed denies from **{role.name}**: {', '.join(items)}")

    @cl.command(name="undenyuser")
    @checks.is_owner()
    async def cl_undenyuser(
        self, ctx: commands.Context, member_input: str, *items: str
    ):
        member = await self._resolve_member(ctx, member_input)
        if not member:
            return await ctx.send("❌ User not found.")
        denied = await self.config.guild(ctx.guild).denied_users()
        if str(member.id) not in denied:
            return await ctx.send("⚠️ User has no denies.")
        current = set(denied[str(member.id)]["cogs"])
        current.difference_update(items)
        denied[str(member.id)]["cogs"] = list(current)
        await self.config.guild(ctx.guild).denied_users.set(denied)
        await ctx.send(f"✅ Removed denies from **{member}**: {', '.join(items)}")

    @cl.command(name="status")
    @checks.is_owner()
    async def cl_status(self, ctx: commands.Context):
        guild = ctx.guild
        data = await self.config.guild(guild).all()
        lockdown = data.get("lockdown_enabled", False)

        embed = discord.Embed(
            title="Command Lockdown Status",
            color=discord.Color.red() if lockdown else discord.Color.green(),
        )
        embed.add_field(
            name="Lockdown Active",
            value="✅ Yes" if lockdown else "❌ No",
            inline=False,
        )

        def format_entries(entries, is_user=False):
            lines = []
            for id_, info in entries.items():
                obj = (
                    guild.get_member(int(id_)) if is_user else guild.get_role(int(id_))
                )
                name = (
                    str(obj)
                    if obj
                    else f"[Unknown {'User' if is_user else 'Role'} {id_}]"
                )
                if info.get("access") == "all":
                    lines.append(f"**{name}** → All")
                else:
                    lines.append(
                        f"**{name}** → {', '.join(info.get('cogs', [])) or 'None'}"
                    )
            return lines or ["None"]

        embed.add_field(
            name="Trusted Roles",
            value="\n".join(format_entries(data["trusted_roles"], False)),
            inline=False,
        )
        embed.add_field(
            name="Trusted Users",
            value="\n".join(format_entries(data["trusted_users"], True)),
            inline=False,
        )

        def format_denies(entries, is_user=False):
            lines = []
            for id_, info in entries.items():
                obj = (
                    guild.get_member(int(id_)) if is_user else guild.get_role(int(id_))
                )
                name = (
                    str(obj)
                    if obj
                    else f"[Unknown {'User' if is_user else 'Role'} {id_}]"
                )
                lines.append(
                    f"**{name}** → {', '.join(info.get('cogs', [])) or 'None'}"
                )
            return lines or ["None"]

        embed.add_field(
            name="Denied Roles",
            value="\n".join(format_denies(data["denied_roles"], False)),
            inline=False,
        )
        embed.add_field(
            name="Denied Users",
            value="\n".join(format_denies(data["denied_users"], True)),
            inline=False,
        )

        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
