import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import List


class CommandLockdown(commands.Cog):
    """Advanced Command Lockdown"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=84738293048, force_registration=True
        )

        self.config.register_guild(
            lockdown_enabled=False,
            trusted_roles={},
            trusted_users={},
            disabled_items=[],
            global_trusted_users=[],
            global_trusted_roles={},
            supertrusted_users=[],
        )

        self._original_checks = list(getattr(self.bot, "_checks", []))
        for chk in self._original_checks:
            try:
                self.bot.remove_check(chk)
            except Exception:
                pass

        self.bot.add_check(self._global_lockdown_check)

    def cog_unload(self):
        try:
            self.bot.remove_check(self._global_lockdown_check)
        except Exception:
            pass
        for chk in self._original_checks:
            try:
                self.bot.add_check(chk)
            except Exception:
                pass

    # ---------------- VALIDATION ----------------

    def _validate_item(self, item: str) -> bool:
        if "." not in item:
            return any(
                cog.qualified_name.lower() == item.lower()
                for cog in self.bot.cogs.values()
            )
        return self.bot.get_command(item.lower()) is not None

    # ---------------- GLOBAL CHECK ----------------

    async def _global_lockdown_check(self, ctx):
        if ctx.guild is None:
            return True

        gid = ctx.guild.id
        data = await self.config.guild(ctx.guild).all()

        # OWNER / SUPERTRUST
        if ctx.author.id in getattr(self.bot, "owner_ids", set()):
            return True

        if ctx.author.id in data["supertrusted_users"]:
            return True

        # COMMAND INFO
        if not ctx.command:
            return True

        cog_name = ctx.cog.qualified_name.lower() if ctx.cog else None
        cmd_name = ctx.command.qualified_name.lower()
        full_cmd = f"{cog_name}.{cmd_name}" if cog_name else None

        # GLOBAL DISABLE
        blocked = False
        for item in data["disabled_items"]:
            if item == cog_name or item == full_cmd:
                blocked = True
                break

        # GLOBAL TRUST BYPASS
        if blocked:
            if ctx.author.id in data["global_trusted_users"]:
                return True

            for r in ctx.author.roles:
                info = data["global_trusted_roles"].get(str(r.id))
                if info:
                    if info == "all":
                        return True
                    if item in info:
                        return True
            return False

        # SERVER LOCKDOWN
        if not data["lockdown_enabled"]:
            return True

        # SERVER TRUST
        if str(ctx.author.id) in data["trusted_users"]:
            info = data["trusted_users"][str(ctx.author.id)]
            if info["access"] == "all":
                return True
            if full_cmd in info["cogs"] or cog_name in info["cogs"]:
                return True

        for r in ctx.author.roles:
            info = data["trusted_roles"].get(str(r.id))
            if info:
                if info["access"] == "all":
                    return True
                if full_cmd in info["cogs"] or cog_name in info["cogs"]:
                    return True

        return False

    # ---------------- COMMAND GROUP ----------------

    @commands.group(name="cl", invoke_without_command=True)
    @checks.is_owner()
    async def cl(self, ctx):
        await ctx.send_help()

    # ---------------- LOCKDOWN ----------------

    @cl.command()
    async def toggle(self, ctx):
        v = await self.config.guild(ctx.guild).lockdown_enabled()
        await self.config.guild(ctx.guild).lockdown_enabled.set(not v)
        await ctx.send(f"🔒 Lockdown {'enabled' if not v else 'disabled'}")

    # ---------------- GLOBAL DISABLE ----------------

    @cl.command(name="globaldisable", aliases=["gdisable"])
    async def globaldisable(self, ctx, item: str):
        item = item.lower()
        if not self._validate_item(item):
            return await ctx.send("❌ Invalid cog or command.")

        data = await self.config.guild(ctx.guild).disabled_items()
        if item in data:
            return await ctx.send("❌ Already disabled.")

        data.append(item)
        await self.config.guild(ctx.guild).disabled_items.set(data)
        await ctx.send(f"🚫 Globally disabled `{item}`")

    @cl.command(name="globalenable", aliases=["genable"])
    async def globalenable(self, ctx, item: str):
        item = item.lower()
        data = await self.config.guild(ctx.guild).disabled_items()
        if item not in data:
            return await ctx.send("❌ Not disabled.")

        data.remove(item)
        await self.config.guild(ctx.guild).disabled_items.set(data)
        await ctx.send(f"✅ Globally enabled `{item}`")

    @cl.command()
    async def globallist(self, ctx):
        data = await self.config.guild(ctx.guild).disabled_items()
        if not data:
            return await ctx.send("No globally disabled commands.")
        await ctx.send(
            "🚫 **Globally Disabled:**\n" + "\n".join(f"`{i}`" for i in data)
        )

    # ---------------- GLOBAL TRUST ----------------

    @cl.command()
    async def globaltrust(self, ctx, member: discord.Member, *items):
        data = await self.config.guild(ctx.guild).global_trusted_users()
        if member.id not in data:
            data.append(member.id)
            await self.config.guild(ctx.guild).global_trusted_users.set(data)
        await ctx.send(f"✅ {member} can bypass global disables")

    @cl.command()
    async def globaluntrust(self, ctx, member: discord.Member):
        data = await self.config.guild(ctx.guild).global_trusted_users()
        if member.id in data:
            data.remove(member.id)
            await self.config.guild(ctx.guild).global_trusted_users.set(data)
        await ctx.send(f"❌ Removed global trust from {member}")

    # ---------------- SUPERTRUST ----------------

    @cl.command()
    async def supertrust(self, ctx, member: discord.Member):
        data = await self.config.guild(ctx.guild).supertrusted_users()
        if member.id not in data:
            data.append(member.id)
            await self.config.guild(ctx.guild).supertrusted_users.set(data)
        await ctx.send(f"⭐ {member} is now SUPERTRUSTED")

    @cl.command()
    async def superuntrust(self, ctx, member: discord.Member):
        data = await self.config.guild(ctx.guild).supertrusted_users()
        if member.id in data:
            data.remove(member.id)
            await self.config.guild(ctx.guild).supertrusted_users.set(data)
        await ctx.send(f"❌ Removed SUPERTRUST from {member}")

    @cl.command()
    async def superlist(self, ctx):
        data = await self.config.guild(ctx.guild).supertrusted_users()
        if not data:
            return await ctx.send("No supertrusted users.")
        users = [ctx.guild.get_member(i) for i in data if ctx.guild.get_member(i)]
        await ctx.send(
            "⭐ **Supertrusted Users:**\n" + "\n".join(str(u) for u in users)
        )


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))