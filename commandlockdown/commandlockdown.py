from redbot.core import commands, Config
import discord


class CommandLockdown(commands.Cog):
    """Server lockdown + global command disable system"""

    def __init__(self, bot):
        self.bot = bot

        # ===== CONFIG =====
        self.config = Config.get_conf(
            self, identifier=9384759384, force_registration=True
        )

        # ORIGINAL (server-level)
        self.config.register_guild(enabled=False, trusted_users=[], trusted_roles=[])

        # NEW (global)
        self.config.register_global(
            globally_disabled=[], global_trusted_users=[], supertrusted_users=[]
        )

    # ======================================================
    # =================== VALIDATION =======================
    # ======================================================

    def _validate_item(self, item: str) -> bool:
        if "." not in item:
            return any(
                cog.qualified_name.lower() == item.lower()
                for cog in self.bot.cogs.values()
            )
        return self.bot.get_command(item) is not None

    # ======================================================
    # =================== CHECK LOGIC ======================
    # ======================================================

    async def _is_supertrusted(self, user: discord.User) -> bool:
        if await self.bot.is_owner(user):
            return True
        return user.id in await self.config.supertrusted_users()

    async def _is_global_trusted(self, user: discord.User) -> bool:
        return user.id in await self.config.global_trusted_users()

    async def _is_server_trusted(self, ctx: commands.Context) -> bool:
        data = await self.config.guild(ctx.guild).all()

        if ctx.author.id in data["trusted_users"]:
            return True

        if any(r.id in data["trusted_roles"] for r in ctx.author.roles):
            return True

        return False

    async def _globally_disabled(self, ctx: commands.Context) -> bool:
        disabled = await self.config.globally_disabled()
        if not disabled:
            return False

        cmd = ctx.command
        if not cmd:
            return False

        qn = cmd.qualified_name
        cog = cmd.cog_name

        for item in disabled:
            if item.lower() == qn.lower():
                return True
            if cog and item.lower() == cog.lower():
                return True

        return False

    # ======================================================
    # =================== MAIN CHECK =======================
    # ======================================================

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        if not ctx.guild or not ctx.command:
            return

        # Owner / supertrust bypass everything
        if await self._is_supertrusted(ctx.author):
            return

        # GLOBAL DISABLE
        if await self._globally_disabled(ctx):
            if await self._is_global_trusted(ctx.author):
                return
            await ctx.send("🚫 This command is globally disabled.")
            raise commands.CheckFailure()

        # SERVER LOCKDOWN
        if not await self.config.guild(ctx.guild).enabled():
            return

        if await self._is_server_trusted(ctx):
            return

        await ctx.send("🔒 Server is in lockdown.")
        raise commands.CheckFailure()

    # ======================================================
    # ================= COMMAND GROUP ======================
    # ======================================================

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def cl(self, ctx):
        """Command lockdown controls"""

    # ======================================================
    # =============== ORIGINAL COMMANDS ====================
    # ======================================================

    @cl.command()
    async def toggle(self, ctx):
        guild = self.config.guild(ctx.guild)
        state = not await guild.enabled()
        await guild.enabled.set(state)
        await ctx.send(f"🔒 Lockdown {'enabled' if state else 'disabled'}.")

    @cl.command()
    async def trust(self, ctx, target: discord.Member | discord.Role):
        guild = self.config.guild(ctx.guild)
        data = await guild.all()

        if isinstance(target, discord.Role):
            if target.id not in data["trusted_roles"]:
                data["trusted_roles"].append(target.id)
                await guild.trusted_roles.set(data["trusted_roles"])
        else:
            if target.id not in data["trusted_users"]:
                data["trusted_users"].append(target.id)
                await guild.trusted_users.set(data["trusted_users"])

        await ctx.send(f"✅ Trusted {target.mention} (server lockdown).")

    @cl.command()
    async def untrust(self, ctx, target: discord.Member | discord.Role):
        guild = self.config.guild(ctx.guild)
        data = await guild.all()

        if isinstance(target, discord.Role):
            if target.id in data["trusted_roles"]:
                data["trusted_roles"].remove(target.id)
                await guild.trusted_roles.set(data["trusted_roles"])
        else:
            if target.id in data["trusted_users"]:
                data["trusted_users"].remove(target.id)
                await guild.trusted_users.set(data["trusted_users"])

        await ctx.send(f"❌ Untrusted {target.mention} (server lockdown).")

    @cl.command()
    async def status(self, ctx):
        """ORIGINAL STATUS — UNCHANGED"""
        data = await self.config.guild(ctx.guild).all()

        embed = discord.Embed(
            title="🔒 Command Lockdown Status", color=discord.Color.orange()
        )

        embed.add_field(
            name="Lockdown",
            value="Enabled" if data["enabled"] else "Disabled",
            inline=False,
        )

        users = [f"<@{u}>" for u in data["trusted_users"]]
        roles = [f"<@&{r}>" for r in data["trusted_roles"]]

        embed.add_field(
            name="Trusted Users",
            value=", ".join(users) if users else "None",
            inline=False,
        )

        embed.add_field(
            name="Trusted Roles",
            value=", ".join(roles) if roles else "None",
            inline=False,
        )

        await ctx.send(embed=embed)

    # ======================================================
    # =============== GLOBAL DISABLE =======================
    # ======================================================

    @cl.command(name="globaldisable", aliases=["gdisable"])
    @commands.is_owner()
    async def global_disable(self, ctx, item: str):
        if not self._validate_item(item):
            await ctx.send("❌ That cog or command does not exist.")
            return

        disabled = await self.config.globally_disabled()
        if item.lower() not in [i.lower() for i in disabled]:
            disabled.append(item)
            await self.config.globally_disabled.set(disabled)

        await ctx.send(f"🚫 Globally disabled `{item}`.")

    @cl.command(name="globalenable", aliases=["genable"])
    @commands.is_owner()
    async def global_enable(self, ctx, item: str):
        disabled = await self.config.globally_disabled()
        disabled = [i for i in disabled if i.lower() != item.lower()]
        await self.config.globally_disabled.set(disabled)
        await ctx.send(f"✅ Globally enabled `{item}`.")

    @cl.command()
    @commands.is_owner()
    async def globallist(self, ctx):
        disabled = await self.config.globally_disabled()
        await ctx.send(
            "**Globally Disabled:**\n" + ("\n".join(disabled) if disabled else "None")
        )

    # ======================================================
    # =============== GLOBAL TRUST =========================
    # ======================================================

    @cl.command()
    @commands.is_owner()
    async def globaltrust(self, ctx, user: discord.User):
        users = await self.config.global_trusted_users()
        if user.id not in users:
            users.append(user.id)
            await self.config.global_trusted_users.set(users)
        await ctx.send(f"🌍 Globally trusted {user.mention}.")

    @cl.command()
    @commands.is_owner()
    async def globaluntrust(self, ctx, user: discord.User):
        users = await self.config.global_trusted_users()
        if user.id in users:
            users.remove(user.id)
            await self.config.global_trusted_users.set(users)
        await ctx.send(f"❌ Removed global trust from {user.mention}.")

    # ======================================================
    # =============== SUPERTRUST ===========================
    # ======================================================

    @cl.command()
    @commands.is_owner()
    async def supertrust(self, ctx, user: discord.User):
        users = await self.config.supertrusted_users()
        if user.id not in users:
            users.append(user.id)
            await self.config.supertrusted_users.set(users)
        await ctx.send(f"👑 Supertrusted {user.mention}.")

    @cl.command()
    @commands.is_owner()
    async def superuntrust(self, ctx, user: discord.User):
        users = await self.config.supertrusted_users()
        if user.id in users:
            users.remove(user.id)
            await self.config.supertrusted_users.set(users)
        await ctx.send(f"❌ Removed supertrust from {user.mention}.")

    @cl.command()
    @commands.is_owner()
    async def superlist(self, ctx):
        users = await self.config.supertrusted_users()
        await ctx.send(
            "**Supertrusted Users:**\n"
            + ("\n".join(f"<@{u}>" for u in users) if users else "None")
        )
