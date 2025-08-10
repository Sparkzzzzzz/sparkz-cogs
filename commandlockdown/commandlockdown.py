import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import Optional, Dict, Any, List


class CommandLockdown(commands.Cog):
    """
    CommandLockdown (Nuke mode)

    - Toggles a global lockdown (cl toggle).
    - cl trust <role> all            -> role gets access to all cogs during lockdown
    - cl trust <role> CogName Cog2   -> role gets access to listed cogs (case-insensitive match)
    - cl untrust <role>              -> removes trust (accepts mention, raw id, or exact name)
    - cl status                      -> nice embed showing lockdown + trusted roles (role names, no pings)

    Nuke behavior:
    - On load this cog REMOVES all existing global checks (bot-level checks) and replaces them with
      this cog's global lockdown check. This prevents other cogs' lingering global checks from blocking commands.
    - On unload this cog removes its global check and RESTORES the original global checks it removed.
      (If other cogs add new checks while this cog is loaded, those new checks will not be restored by this cog.)
    """

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot
        self.config: Config = Config.get_conf(
            self, identifier=84738293048, force_registration=True
        )
        self.config.register_guild(
            lockdown_enabled=False,
            # trusted_roles : mapping str(role_id) -> {"access": "all"|"cogs", "cogs": [cogname,...]}
            trusted_roles={},
        )

        # Capture and nuke other global checks immediately on load.
        # Save originals for restoration on unload.
        self._original_checks: List = []
        try:
            existing = getattr(self.bot, "_checks", None)
            if existing is None:
                existing = []
            else:
                existing = list(existing)
        except Exception:
            existing = []

        # remove all existing checks and store them
        for chk in existing:
            try:
                self.bot.remove_check(chk)
                self._original_checks.append(chk)
            except Exception:
                # best-effort: ignore failures
                pass

        # add our global lockdown check
        self.bot.add_check(self._global_lockdown_check)

    def cog_unload(self) -> None:
        """Restore original global checks when the cog unloads and remove our check."""
        try:
            # remove our check
            self.bot.remove_check(self._global_lockdown_check)
        except Exception:
            pass

        # restore previously removed checks
        for chk in self._original_checks:
            try:
                self.bot.add_check(chk)
            except Exception:
                pass

    # -----------------------
    # Helpers
    # -----------------------
    async def _resolve_role(
        self, ctx: commands.Context, role_input: str
    ) -> Optional[discord.Role]:
        """
        Resolve role_input which can be:
         - a mention: <@&ID>
         - an ID string
         - an exact name (case-insensitive)
        Returns discord.Role or None.
        """
        # mention
        if role_input.startswith("<@&") and role_input.endswith(">"):
            inner = role_input[3:-1]
            if inner.isdigit():
                return ctx.guild.get_role(int(inner))

        # raw id
        if role_input.isdigit():
            r = ctx.guild.get_role(int(role_input))
            if r:
                return r

        # exact name (case-insensitive)
        name = role_input.strip()
        for r in ctx.guild.roles:
            if r.name.lower() == name.lower():
                return r

        # not found
        return None

    def _format_cogs(self, cogs: List[str]) -> List[str]:
        """Normalize cog names to displayable list (preserve original case as provided)."""
        return list(cogs)

    # -----------------------
    # Global lockdown check
    # -----------------------
    async def _global_lockdown_check(self, ctx: commands.Context) -> bool:
        """
        Global check that runs for EVERY command.
        Returns True to allow, raises CheckFailure (or returns False) to block.
        """
        # Always allow bot owners (supports multiple owners)
        try:
            if await self.bot.is_owner(ctx.author):
                return True
        except Exception:
            # fallback: check owner_ids if available
            if hasattr(self.bot, "owner_ids") and ctx.author.id in getattr(
                self.bot, "owner_ids", set()
            ):
                return True

        # Allow DMs and contexts without guild
        if ctx.guild is None:
            return True

        data = await self.config.guild(ctx.guild).all()
        if not data.get("lockdown_enabled", False):
            return True  # lockdown is off

        trusted: Dict[str, Dict[str, Any]] = data.get("trusted_roles", {}) or {}
        user_role_ids = {str(r.id) for r in ctx.author.roles}

        # Build allowed cogs set from all matching trusted roles the user has
        allowed_cogs_lower = set()
        allow_all = False
        for rid, info in trusted.items():
            if str(rid) in user_role_ids:
                access = info.get("access", "all")
                if access == "all":
                    allow_all = True
                    break
                cogs = info.get("cogs", []) or []
                for c in cogs:
                    allowed_cogs_lower.add(c.lower())

        if allow_all:
            return True

        # If command has no cog (maybe a bare command), treat as blocked unless allowed explicitly by 'all'
        cog_name = None
        if ctx.cog:
            # prefer qualified_name, fallback to cog name
            cog_name = (
                getattr(ctx.cog, "qualified_name", None) or ctx.cog.__class__.__name__
            )
            if cog_name and cog_name.lower() in allowed_cogs_lower:
                return True

        # not allowed
        return False

    # -----------------------
    # Commands - owner only for management
    # -----------------------
    @commands.group(name="cl", invoke_without_command=True)
    @checks.is_owner()
    async def cl(self, ctx: commands.Context):
        """Command Lockdown management (owner-only)."""
        await ctx.send_help()

    @cl.command(name="toggle")
    @checks.is_owner()
    async def cl_toggle(self, ctx: commands.Context):
        """Toggle global lockdown on/off."""
        guild = ctx.guild
        current = await self.config.guild(guild).lockdown_enabled()
        await self.config.guild(guild).lockdown_enabled.set(not current)
        await ctx.send(
            embed=discord.Embed(
                title="Command Lockdown",
                description=f"🔒 Lockdown is now {'**ON**' if not current else '**OFF**'}",
                color=discord.Color.red() if not current else discord.Color.green(),
            )
        )

    @cl.command(name="trust")
    @checks.is_owner()
    async def cl_trust(self, ctx: commands.Context, role_input: str, *cogs: str):
        """
        Trust a role.
        role_input: mention, id, or exact name
        cogs: either 'all' or list of cog names (space-separated)
        Examples:
          cl trust 1374786420241203302 all
          cl trust "Moderators" Mod Cleanup
        """
        guild = ctx.guild
        role = await self._resolve_role(ctx, role_input)
        if not role:
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"Role `{role_input}` not found in this server.",
                    color=discord.Color.red(),
                )
            )
            return

        trusted = await self.config.guild(guild).trusted_roles()
        if len(cogs) == 0:
            # default to all
            trusted[str(role.id)] = {"access": "all", "cogs": []}
        elif len(cogs) == 1 and cogs[0].lower() == "all":
            trusted[str(role.id)] = {"access": "all", "cogs": []}
        else:
            # store as provided (case-insensitive matching done at check-time)
            trusted[str(role.id)] = {"access": "cogs", "cogs": list(cogs)}

        await self.config.guild(guild).trusted_roles.set(trusted)

        cogs_display = (
            "All"
            if trusted[str(role.id)]["access"] == "all"
            else ", ".join(trusted[str(role.id)]["cogs"])
        )
        await ctx.send(
            embed=discord.Embed(
                title="Role Trusted",
                description=f"✅ Role **{role.name}** trusted for: {cogs_display}",
                color=discord.Color.green(),
            )
        )

    @cl.command(name="untrust")
    @checks.is_owner()
    async def cl_untrust(self, ctx: commands.Context, role_input: str):
        """
        Untrust a role. Accepts mention, raw id, or exact name.
        """
        guild = ctx.guild
        role = await self._resolve_role(ctx, role_input)
        role_id = None
        role_name = None
        if role:
            role_id = str(role.id)
            role_name = role.name
        elif role_input.isdigit():
            role_id = role_input
            role_name = f"Unknown Role ({role_input})"
        else:
            # not resolvable
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"Role `{role_input}` not found. Use mention, raw ID, or exact role name.",
                    color=discord.Color.red(),
                )
            )
            return

        trusted = await self.config.guild(guild).trusted_roles()
        if role_id in trusted:
            del trusted[role_id]
            await self.config.guild(guild).trusted_roles.set(trusted)
            await ctx.send(
                embed=discord.Embed(
                    title="Role Untrusted",
                    description=f"✅ Role **{role_name}** has been removed from trusted list.",
                    color=discord.Color.green(),
                )
            )
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="Not Trusted",
                    description=f"⚠️ Role **{role_name}** is not in the trusted list.",
                    color=discord.Color.orange(),
                )
            )

    @cl.command(name="status")
    @checks.is_owner()
    async def cl_status(self, ctx: commands.Context):
        """Show current lockdown status and trusted roles (role names shown)."""
        guild = ctx.guild
        data = await self.config.guild(guild).all()
        lockdown = data.get("lockdown_enabled", False)
        trusted = data.get("trusted_roles", {}) or {}

        embed = discord.Embed(
            title="Command Lockdown Status",
            color=discord.Color.red() if lockdown else discord.Color.green(),
        )
        embed.add_field(
            name="Lockdown Active",
            value="✅ Yes" if lockdown else "❌ No",
            inline=False,
        )

        if not trusted:
            embed.add_field(name="Trusted Roles", value="None", inline=False)
        else:
            lines = []
            for rid, info in trusted.items():
                role_obj = guild.get_role(int(rid))
                role_name = role_obj.name if role_obj else f"[Unknown Role {rid}]"
                if info.get("access") == "all":
                    lines.append(f"**{role_name}** → All")
                else:
                    lines.append(
                        f"**{role_name}** → {', '.join(info.get('cogs', [])) or 'None'}"
                    )
            embed.add_field(name="Trusted Roles", value="\n".join(lines), inline=False)

        await ctx.send(embed=embed)


async def setup(bot: Red):
    await bot.add_cog(CommandLockdown(bot))
