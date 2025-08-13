import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import List


class CommandLockdown(commands.Cog):
    """
    CommandLockdown with:
    - Role/User allow lists (full, cog-level, command-level)
    - Role/User deny lists (cog-level, command-level)
    - Deny always overrides allow
    - Improved status display with multi-line tables
    - Add/Remove individual cogs/commands without overwriting
    """

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot
        self.config: Config = Config.get_conf(
            self, identifier=84738293048, force_registration=True
        )
        self.config.register_guild(
            lockdown_enabled=False,
            trusted_roles={},
            trusted_users={},
            denied_roles={},
            denied_users={},
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

    async def _resolve_role(self, ctx, role_input: str):
        if role_input.startswith("<@&") and role_input.endswith(">"):
            inner = role_input[3:-1]
            if inner.isdigit():
                return ctx.guild.get_role(int(inner))
        if role_input.isdigit():
            return ctx.guild.get_role(int(role_input))
        for r in ctx.guild.roles:
            if r.name.lower() == role_input.lower():
                return r
        return None

    async def _resolve_member(self, ctx, member_input: str):
        if member_input.startswith("<@") and member_input.endswith(">"):
            inner = member_input.strip("<@!>")
            if inner.isdigit():
                return ctx.guild.get_member(int(inner))
        if member_input.isdigit():
            return ctx.guild.get_member(int(member_input))
        for m in ctx.guild.members:
            if (
                m.name.lower() == member_input.lower()
                or f"{m.name.lower()}#{m.discriminator}" == member_input.lower()
            ):
                return m
        return None

    async def _is_match(self, items: List[str], ctx):
        cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
        cmd_name = ctx.command.qualified_name.lower() if ctx.command else None
        full_cmd = f"{cog_name}.{cmd_name}" if cog_name and cmd_name else None
        items_lower = {i.lower() for i in items}
        return (cog_name and cog_name in items_lower) or (
            full_cmd and full_cmd in items_lower
        )

    async def _global_lockdown_check(self, ctx):
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
        if not data["lockdown_enabled"]:
            return True

        tr_roles, tr_users = data["trusted_roles"], data["trusted_users"]
        dr_roles, dr_users = data["denied_roles"], data["denied_users"]
        user_roles = {str(r.id) for r in ctx.author.roles}

        # Deny check first
        if str(ctx.author.id) in dr_users and await self._is_match(
            dr_users[str(ctx.author.id)]["cogs"], ctx
        ):
            return False
        for rid, info in dr_roles.items():
            if rid in user_roles and await self._is_match(info["cogs"], ctx):
                return False

        # Allow check
        if str(ctx.author.id) in tr_users:
            info = tr_users[str(ctx.author.id)]
            if info["access"] == "all" or await self._is_match(info["cogs"], ctx):
                return True
        allowed_items = set()
        allow_all = False
        for rid, info in tr_roles.items():
            if rid in user_roles:
                if info["access"] == "all":
                    allow_all = True
                    break
                allowed_items.update(info["cogs"])
        return allow_all or await self._is_match(list(allowed_items), ctx)

    @commands.group(name="cl", invoke_without_command=True)
    @checks.is_owner()
    async def cl(self, ctx):
        """Command Lockdown management."""
        await ctx.send_help()

    @cl.command()
    @checks.is_owner()
    async def toggle(self, ctx):
        """Toggle lockdown on or off."""
        current = await self.config.guild(ctx.guild).lockdown_enabled()
        await self.config.guild(ctx.guild).lockdown_enabled.set(not current)
        await ctx.send(f"🔒 Lockdown is now {'ON' if not current else 'OFF'}.")

    # ===== TRUST / UNTRUST =====
    @cl.command()
    @checks.is_owner()
    async def trust(self, ctx, target: str, *items: str):
        """Trust a role or user for all or specific cogs/commands."""
        obj = await self._resolve_role(ctx, target) or await self._resolve_member(
            ctx, target
        )
        if not obj:
            return await ctx.send("❌ Role or user not found.")
        if isinstance(obj, discord.Member):
            tu = await self.config.guild(ctx.guild).trusted_users()
            current = tu.get(str(obj.id), {"access": "cogs", "cogs": []})
            if not items or items[0].lower() == "all":
                current = {"access": "all", "cogs": []}
            else:
                if current.get("access") != "all":
                    current["cogs"] = list(set(current.get("cogs", [])) | set(items))
                    current["access"] = "cogs"
            tu[str(obj.id)] = current
            await self.config.guild(ctx.guild).trusted_users.set(tu)
        else:
            tr = await self.config.guild(ctx.guild).trusted_roles()
            current = tr.get(str(obj.id), {"access": "cogs", "cogs": []})
            if not items or items[0].lower() == "all":
                current = {"access": "all", "cogs": []}
            else:
                if current.get("access") != "all":
                    current["cogs"] = list(set(current.get("cogs", [])) | set(items))
                    current["access"] = "cogs"
            tr[str(obj.id)] = current
            await self.config.guild(ctx.guild).trusted_roles.set(tr)
        await ctx.send(f"✅ {obj} trusted for: {', '.join(items) if items else 'All'}")

    @cl.command()
    @checks.is_owner()
    async def untrust(self, ctx, target: str, *items: str):
        """Remove trust from a role or user for specific cogs/commands."""
        obj = await self._resolve_role(ctx, target) or await self._resolve_member(
            ctx, target
        )
        if not obj:
            return await ctx.send("❌ Role or user not found.")
        if isinstance(obj, discord.Member):
            tu = await self.config.guild(ctx.guild).trusted_users()
            current = tu.get(str(obj.id))
            if not current or current.get("access") == "all":
                return await ctx.send("❌ User has full access or is not trusted.")
            current["cogs"] = list(set(current.get("cogs", [])) - set(items))
            if not current["cogs"]:
                tu.pop(str(obj.id))
            else:
                tu[str(obj.id)] = current
            await self.config.guild(ctx.guild).trusted_users.set(tu)
        else:
            tr = await self.config.guild(ctx.guild).trusted_roles()
            current = tr.get(str(obj.id))
            if not current or current.get("access") == "all":
                return await ctx.send("❌ Role has full access or is not trusted.")
            current["cogs"] = list(set(current.get("cogs", [])) - set(items))
            if not current["cogs"]:
                tr.pop(str(obj.id))
            else:
                tr[str(obj.id)] = current
            await self.config.guild(ctx.guild).trusted_roles.set(tr)
        await ctx.send(f"✅ Removed {', '.join(items)} from {obj} trust list.")

    # ===== DENY / UNDENY =====
    @cl.command()
    @checks.is_owner()
    async def deny(self, ctx, target: str, *items: str):
        """Deny a role or user for specific cogs/commands."""
        obj = await self._resolve_role(ctx, target) or await self._resolve_member(
            ctx, target
        )
        if not obj:
            return await ctx.send("❌ Role or user not found.")
        if isinstance(obj, discord.Member):
            du = await self.config.guild(ctx.guild).denied_users()
            current = set(du.get(str(obj.id), {}).get("cogs", []))
            current.update(items)
            du[str(obj.id)] = {"cogs": list(current)}
            await self.config.guild(ctx.guild).denied_users.set(du)
        else:
            dr = await self.config.guild(ctx.guild).denied_roles()
            current = set(dr.get(str(obj.id), {}).get("cogs", []))
            current.update(items)
            dr[str(obj.id)] = {"cogs": list(current)}
            await self.config.guild(ctx.guild).denied_roles.set(dr)
        await ctx.send(f"⛔ {obj} denied for: {', '.join(items)}")

    @cl.command()
    @checks.is_owner()
    async def undeny(self, ctx, target: str, *items: str):
        """Remove deny from a role or user for specific cogs/commands."""
        obj = await self._resolve_role(ctx, target) or await self._resolve_member(
            ctx, target
        )
        if not obj:
            return await ctx.send("❌ Role or user not found.")
        if isinstance(obj, discord.Member):
            du = await self.config.guild(ctx.guild).denied_users()
            current = set(du.get(str(obj.id), {}).get("cogs", []))
            current -= set(items)
            if current:
                du[str(obj.id)] = {"cogs": list(current)}
            else:
                du.pop(str(obj.id), None)
            await self.config.guild(ctx.guild).denied_users.set(du)
        else:
            dr = await self.config.guild(ctx.guild).denied_roles()
            current = set(dr.get(str(obj.id), {}).get("cogs", []))
            current -= set(items)
            if current:
                dr[str(obj.id)] = {"cogs": list(current)}
            else:
                dr.pop(str(obj.id), None)
            await self.config.guild(ctx.guild).denied_roles.set(dr)
        await ctx.send(f"✅ Removed {', '.join(items)} from {obj} deny list.")

    # ===== STATUS =====
    @cl.command()
    @checks.is_owner()
    async def status(self, ctx):
        """Show current lockdown status with trusted and denied lists."""
        data = await self.config.guild(ctx.guild).all()

        def format_multiline_table(title, entries, is_user=False):
            if not entries:
                return f"**{title}:** None\n"
            lines = []
            header = f"{title[:-1]:<25} Access/Items"
            lines.append(header)
            lines.append("-" * len(header))
            for id_, info in sorted(entries.items(), key=lambda x: x[0]):
                obj = (
                    ctx.guild.get_member(int(id_))
                    if is_user
                    else ctx.guild.get_role(int(id_))
                )
                name = (
                    str(obj)
                    if obj
                    else f"[Unknown {'User' if is_user else 'Role'} {id_}]"
                )
                access = info.get("access", "")
                if access == "all":
                    items_list = ["All"]
                else:
                    items_list = info.get("cogs", [])
                if items_list:
                    first_line = f"{name:<25} {items_list[0]}"
                    lines.append(first_line)
                    for item in items_list[1:]:
                        lines.append(f"{'':<25} {item}")
                else:
                    lines.append(f"{name:<25} None")
                lines.append("")
            return f"**{title}:**\n```" + "\n".join(lines) + "```"

        embed = discord.Embed(
            title="Command Lockdown Status",
            description=f"Lockdown Active: {'✅ Yes' if data['lockdown_enabled'] else '❌ No'}",
            color=(
                discord.Color.red()
                if data["lockdown_enabled"]
                else discord.Color.green()
            ),
        )
        embed.add_field(
            name="\u200b",
            value=format_multiline_table("Trusted Roles", data["trusted_roles"]),
            inline=False,
        )
        embed.add_field(
            name="\u200b",
            value=format_multiline_table(
                "Trusted Users", data["trusted_users"], is_user=True
            ),
            inline=False,
        )
        embed.add_field(
            name="\u200b",
            value=format_multiline_table("Denied Roles", data["denied_roles"]),
            inline=False,
        )
        embed.add_field(
            name="\u200b",
            value=format_multiline_table(
                "Denied Users", data["denied_users"], is_user=True
            ),
            inline=False,
        )

        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
