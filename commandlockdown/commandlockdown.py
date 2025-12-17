import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import List


class CommandLockdown(commands.Cog):
    """
    CommandLockdown with:
    - Role/User allow lists (full or specific cogs/commands)
    - Global disable of cogs / commands (owner only)
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
            disabled_items=[],
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

    # ---------- RESOLVERS ----------

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

    # ---------- MATCHING ----------

    async def _is_match(self, items: List[str], ctx):
        cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
        cmd_name = ctx.command.qualified_name.lower() if ctx.command else None
        full_cmd = f"{cog_name}.{cmd_name}" if cog_name and cmd_name else None

        items_lower = {i.lower() for i in items}
        return (cog_name and cog_name in items_lower) or (
            full_cmd and full_cmd in items_lower
        )

    # ---------- VALIDATION ----------

    def _validate_item(self, item: str) -> bool:
        """
        Validates whether a cog or cog.command exists (Red-safe).
        """
        if "." not in item:
            # Validate cog (case-insensitive)
            return any(
                cog.qualified_name.lower() == item.lower()
                for cog in self.bot.cogs.values()
            )

        # Validate command (global lookup, supports subcommands)
        return self.bot.get_command(item) is not None


    # ---------- GLOBAL CHECK ----------

    async def _global_lockdown_check(self, ctx):
        if ctx.guild is None:
            return True

        if ctx.author.id in getattr(self.bot, "owner_ids", set()):
            return True

        data = await self.config.guild(ctx.guild).all()

        # ===== GLOBAL DISABLE =====
        disabled = set(data.get("disabled_items", []))
        blocked_by_disable = False

        if disabled and ctx.command:
            cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
            cmd_name = ctx.command.qualified_name.lower() if ctx.command else None
            full_cmd = f"{cog_name}.{cmd_name}" if cog_name and cmd_name else None

            if (cog_name and cog_name in disabled) or (
                full_cmd and full_cmd in disabled
            ):
                blocked_by_disable = True

        if not data["lockdown_enabled"] and not blocked_by_disable:
            return True

        tr_roles, tr_users = data["trusted_roles"], data["trusted_users"]
        user_roles = {str(r.id) for r in ctx.author.roles}

        # Trusted users
        if str(ctx.author.id) in tr_users:
            info = tr_users[str(ctx.author.id)]
            if info["access"] == "all" or await self._is_match(info["cogs"], ctx):
                return True

        # Trusted roles
        allowed_items = set()
        allow_all = False
        for rid, info in tr_roles.items():
            if rid in user_roles:
                if info["access"] == "all":
                    allow_all = True
                    break
                allowed_items.update(info["cogs"])

        allowed = allow_all or await self._is_match(list(allowed_items), ctx)

        if blocked_by_disable:
            return allowed

        return allowed

    # ---------- COMMANDS ----------

    @commands.group(name="cl", invoke_without_command=True)
    @checks.is_owner()
    async def cl(self, ctx):
        """Command Lockdown management."""
        await ctx.send_help()

    @cl.command()
    @checks.is_owner()
    async def toggle(self, ctx):
        current = await self.config.guild(ctx.guild).lockdown_enabled()
        await self.config.guild(ctx.guild).lockdown_enabled.set(not current)
        await ctx.send(f"🔒 Lockdown is now {'ON' if not current else 'OFF'}.")

    # ---------- TRUST ----------

    @cl.command()
    @checks.is_owner()
    async def trust(self, ctx, target: str, *items: str):
        obj = await self._resolve_role(ctx, target) or await self._resolve_member(
            ctx, target
        )
        if not obj:
            return await ctx.send("❌ Role or user not found.")

        items = [i.lower() for i in items]

        for i in items:
            if i != "all" and not self._validate_item(i):
                return await ctx.send(f"❌ `{i}` is not a valid cog or command.")

        if isinstance(obj, discord.Member):
            tu = await self.config.guild(ctx.guild).trusted_users()
            current = tu.get(str(obj.id), {"access": "cogs", "cogs": []})
            if not items or items[0] == "all":
                current = {"access": "all", "cogs": []}
            else:
                if current.get("access") != "all":
                    current["cogs"] = list(set(current.get("cogs", [])) | set(items))
            tu[str(obj.id)] = current
            await self.config.guild(ctx.guild).trusted_users.set(tu)
        else:
            tr = await self.config.guild(ctx.guild).trusted_roles()
            current = tr.get(str(obj.id), {"access": "cogs", "cogs": []})
            if not items or items[0] == "all":
                current = {"access": "all", "cogs": []}
            else:
                if current.get("access") != "all":
                    current["cogs"] = list(set(current.get("cogs", [])) | set(items))
            tr[str(obj.id)] = current
            await self.config.guild(ctx.guild).trusted_roles.set(tr)

        await ctx.send(f"✅ {obj} trusted for: {', '.join(items) if items else 'All'}")

    # ---------- GLOBAL DISABLE ----------

    @cl.command()
    @checks.is_owner()
    async def disable(self, ctx, item: str):
        item = item.lower()

        if not self._validate_item(item):
            return await ctx.send("❌ That cog or command does not exist.")

        data = await self.config.guild(ctx.guild).disabled_items()
        if item in data:
            return await ctx.send("❌ Already disabled.")

        data.append(item)
        await self.config.guild(ctx.guild).disabled_items.set(data)
        await ctx.send(f"🚫 Disabled `{item}` for everyone except trusted users.")

    @cl.command()
    @checks.is_owner()
    async def enable(self, ctx, item: str):
        item = item.lower()
        data = await self.config.guild(ctx.guild).disabled_items()

        if item not in data:
            return await ctx.send("❌ That item is not disabled.")

        data.remove(item)
        await self.config.guild(ctx.guild).disabled_items.set(data)
        await ctx.send(f"✅ Re-enabled `{item}`.")

    # ---------- STATUS ----------

    @cl.command()
    @checks.is_owner()
    async def status(self, ctx):
        data = await self.config.guild(ctx.guild).all()

        embed = discord.Embed(
            title="Command Lockdown Status",
            description=f"Lockdown Active: {'✅ Yes' if data['lockdown_enabled'] else '❌ No'}",
            color=(
                discord.Color.red()
                if data["lockdown_enabled"]
                else discord.Color.green()
            ),
        )

        disabled = data.get("disabled_items", [])
        embed.add_field(
            name="Globally Disabled",
            value="None" if not disabled else "\n".join(f"`{i}`" for i in disabled),
            inline=False,
        )

        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
