import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import List


class CommandLockdown(commands.Cog):
    """
    CommandLockdown with:
    - Server lockdown (existing)
    - Global disable system (new)
    - Global trust + Supertrust (new)
    """

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot

        # ---------- CONFIG ----------
        self.config: Config = Config.get_conf(
            self, identifier=84738293048, force_registration=True
        )

        # GUILD CONFIG (existing + new)
        self.config.register_guild(
            lockdown_enabled=False,
            trusted_roles={},
            trusted_users={},
            disabled_items=[],  # NEW: global disables
            global_trusted_users=[],  # NEW: bypass global disables only
        )

        # GLOBAL CONFIG (NEW: supertrust)
        self.config.register_global(supertrusted_users=[])

        # ---------- CHECK INJECTION ----------
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

    # ==========================================================
    # RESOLVERS (UNCHANGED)
    # ==========================================================

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

    # ==========================================================
    # MATCHING + VALIDATION
    # ==========================================================

    async def _is_match(self, items: List[str], ctx):
        cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
        cmd_name = ctx.command.qualified_name.lower() if ctx.command else None
        full_cmd = f"{cog_name}.{cmd_name}" if cog_name and cmd_name else None
        items_lower = {i.lower() for i in items}

        return (cog_name and cog_name in items_lower) or (
            full_cmd and full_cmd in items_lower
        )

    def _validate_item(self, item: str) -> bool:
        if "." not in item:
            return any(
                cog.qualified_name.lower() == item.lower()
                for cog in self.bot.cogs.values()
            )
        return self.bot.get_command(item.lower()) is not None

    # ==========================================================
    # GLOBAL CHECK (EXTENDED, NOT REPLACED)
    # ==========================================================

    async def _global_lockdown_check(self, ctx):
        if ctx.guild is None:
            return True

        # BOT OWNER
        if ctx.author.id in getattr(self.bot, "owner_ids", set()):
            return True

        # SUPERTRUST (GLOBAL)
        supertrusted = await self.config.supertrusted_users()
        if ctx.author.id in supertrusted:
            return True

        if not ctx.command:
            return True

        data = await self.config.guild(ctx.guild).all()

        cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
        cmd_name = ctx.command.qualified_name.lower()
        full_cmd = f"{cog_name}.{cmd_name}" if cog_name else None

        # ---------- GLOBAL DISABLE ----------
        if cog_name in data["disabled_items"] or full_cmd in data["disabled_items"]:
            if ctx.author.id in data["global_trusted_users"]:
                return True
            return False

        # ---------- SERVER LOCKDOWN (ORIGINAL LOGIC) ----------
        if not data["lockdown_enabled"]:
            return True

        tr_roles, tr_users = data["trusted_roles"], data["trusted_users"]
        user_roles = {str(r.id) for r in ctx.author.roles}

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

    # ==========================================================
    # COMMAND GROUP (UNCHANGED)
    # ==========================================================

    @commands.group(name="cl", invoke_without_command=True)
    @checks.is_owner()
    async def cl(self, ctx):
        await ctx.send_help()

    @cl.command()
    @checks.is_owner()
    async def toggle(self, ctx):
        current = await self.config.guild(ctx.guild).lockdown_enabled()
        await self.config.guild(ctx.guild).lockdown_enabled.set(not current)
        await ctx.send(f"🔒 Lockdown is now {'ON' if not current else 'OFF'}.")

    # ==========================================================
    # TRUST / UNTRUST (UNCHANGED)
    # ==========================================================

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
                return await ctx.send(f"❌ `{i}` does not exist.")

        if isinstance(obj, discord.Member):
            tu = await self.config.guild(ctx.guild).trusted_users()
            current = tu.get(str(obj.id), {"access": "cogs", "cogs": []})
            if not items or items[0] == "all":
                current = {"access": "all", "cogs": []}
            else:
                current["cogs"] = list(set(current.get("cogs", [])) | set(items))
            tu[str(obj.id)] = current
            await self.config.guild(ctx.guild).trusted_users.set(tu)
        else:
            tr = await self.config.guild(ctx.guild).trusted_roles()
            current = tr.get(str(obj.id), {"access": "cogs", "cogs": []})
            if not items or items[0] == "all":
                current = {"access": "all", "cogs": []}
            else:
                current["cogs"] = list(set(current.get("cogs", [])) | set(items))
            tr[str(obj.id)] = current
            await self.config.guild(ctx.guild).trusted_roles.set(tr)

        await ctx.send(f"✅ {obj} trusted.")

    @cl.command()
    @checks.is_owner()
    async def untrust(self, ctx, target: str, *items: str):
        obj = await self._resolve_role(ctx, target) or await self._resolve_member(
            ctx, target
        )
        if not obj:
            return await ctx.send("❌ Role or user not found.")

        if isinstance(obj, discord.Member):
            tu = await self.config.guild(ctx.guild).trusted_users()
            tu.pop(str(obj.id), None)
            await self.config.guild(ctx.guild).trusted_users.set(tu)
        else:
            tr = await self.config.guild(ctx.guild).trusted_roles()
            tr.pop(str(obj.id), None)
            await self.config.guild(ctx.guild).trusted_roles.set(tr)

        await ctx.send(f"❌ Trust removed from {obj}")

    # ==========================================================
    # GLOBAL DISABLE COMMANDS (NEW)
    # ==========================================================

    @cl.command(name="globaldisable", aliases=["gdisable"])
    @checks.is_owner()
    async def globaldisable(self, ctx, item: str):
        item = item.lower()
        if not self._validate_item(item):
            return await ctx.send("❌ Cog or command does not exist.")

        data = await self.config.guild(ctx.guild).disabled_items()
        if item in data:
            return await ctx.send("❌ Already disabled.")

        data.append(item)
        await self.config.guild(ctx.guild).disabled_items.set(data)
        await ctx.send(f"🚫 Globally disabled `{item}`")

    @cl.command(name="globalenable", aliases=["genable"])
    @checks.is_owner()
    async def globalenable(self, ctx, item: str):
        item = item.lower()
        data = await self.config.guild(ctx.guild).disabled_items()
        if item not in data:
            return await ctx.send("❌ Not disabled.")

        data.remove(item)
        await self.config.guild(ctx.guild).disabled_items.set(data)
        await ctx.send(f"✅ Globally enabled `{item}`")

    @cl.command()
    @checks.is_owner()
    async def globallist(self, ctx):
        data = await self.config.guild(ctx.guild).disabled_items()
        if not data:
            return await ctx.send("No globally disabled commands.")
        await ctx.send(
            "🚫 **Globally Disabled:**\n" + "\n".join(f"`{i}`" for i in data)
        )

    # ==========================================================
    # GLOBAL TRUST (NEW)
    # ==========================================================

    @cl.command()
    @checks.is_owner()
    async def globaltrust(self, ctx, member: discord.Member):
        data = await self.config.guild(ctx.guild).global_trusted_users()
        if member.id not in data:
            data.append(member.id)
            await self.config.guild(ctx.guild).global_trusted_users.set(data)
        await ctx.send(f"✅ {member} can bypass global disables")

    @cl.command()
    @checks.is_owner()
    async def globaluntrust(self, ctx, member: discord.Member):
        data = await self.config.guild(ctx.guild).global_trusted_users()
        if member.id in data:
            data.remove(member.id)
            await self.config.guild(ctx.guild).global_trusted_users.set(data)
        await ctx.send(f"❌ Removed global trust from {member}")

    # ==========================================================
    # SUPERTRUST (GLOBAL, OWNER-LIKE)
    # ==========================================================

    @cl.command()
    @checks.is_owner()
    async def supertrust(self, ctx, member: discord.Member):
        data = await self.config.supertrusted_users()
        if member.id not in data:
            data.append(member.id)
            await self.config.supertrusted_users.set(data)
        await ctx.send(f"⭐ {member} is now SUPERTRUSTED (global)")

    @cl.command()
    @checks.is_owner()
    async def superuntrust(self, ctx, member: discord.Member):
        data = await self.config.supertrusted_users()
        if member.id in data:
            data.remove(member.id)
            await self.config.supertrusted_users.set(data)
        await ctx.send(f"❌ Removed SUPERTRUST from {member}")

    @cl.command()
    @checks.is_owner()
    async def superlist(self, ctx):
        data = await self.config.supertrusted_users()
        if not data:
            return await ctx.send("No supertrusted users.")
        await ctx.send(
            "⭐ **Supertrusted Users:**\n" + "\n".join(f"<@{uid}>" for uid in data)
        )


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
