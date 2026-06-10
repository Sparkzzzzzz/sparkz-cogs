import time

import discord
from redbot.core import commands, Config
from redbot.core.bot import Red


class ChannelRestrict(commands.Cog):
    """
    Restrict all bot commands to a single channel.

    Users without a whitelisted role cannot run commands outside the
    configured channel and get an ephemeral (or auto-deleting) notice
    pointing them to the right channel.
    """

    __version__ = "1.0.0"
    __author__ = "Sparkz"

    def __init__(self, bot: Red):
        self.bot = bot
        self._recent_notices = {}
        self.config = Config.get_conf(
            self, identifier=9847362154, force_registration=True
        )
        default_guild = {
            "channel_id": None,
            "whitelist_roles": [],
            "enabled": False,
        }
        self.config.register_guild(**default_guild)

    def format_help_for_context(self, ctx: commands.Context) -> str:
        pre = super().format_help_for_context(ctx)
        return f"{pre}\n\nVersion: {self.__version__}"

    async def red_delete_data_for_user(self, **kwargs):
        return

    # ---------------------------------------------------------------
    # Settings commands
    # ---------------------------------------------------------------

    @commands.group(name="channelrestrict", aliases=["chrestrict", "crestrict"])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def channelrestrict(self, ctx: commands.Context):
        """Configure bot channel restriction."""

    @channelrestrict.command(name="channel")
    async def cr_channel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Set (or clear) the only channel where bot commands can be used."""
        if channel is None:
            await self.config.guild(ctx.guild).channel_id.set(None)
            return await ctx.send("Restriction channel cleared.")
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(
            f"Bot commands will now be restricted to {channel.mention} (for non-whitelisted users)."
        )

    @channelrestrict.command(name="addrole")
    async def cr_addrole(self, ctx: commands.Context, role: discord.Role):
        """Add a role to the whitelist (can use commands anywhere)."""
        async with self.config.guild(ctx.guild).whitelist_roles() as roles:
            if role.id in roles:
                return await ctx.send("That role is already whitelisted.")
            roles.append(role.id)
        await ctx.send(f"{role.name} added to the whitelist.")

    @channelrestrict.command(name="removerole")
    async def cr_removerole(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from the whitelist."""
        async with self.config.guild(ctx.guild).whitelist_roles() as roles:
            if role.id not in roles:
                return await ctx.send("That role isn't whitelisted.")
            roles.remove(role.id)
        await ctx.send(f"{role.name} removed from the whitelist.")

    @channelrestrict.command(name="toggle")
    async def cr_toggle(self, ctx: commands.Context, on_off: bool = None):
        """Enable or disable the restriction."""
        current = await self.config.guild(ctx.guild).enabled()
        new = on_off if on_off is not None else not current
        await self.config.guild(ctx.guild).enabled.set(new)
        await ctx.send(f"Channel restriction {'enabled' if new else 'disabled'}.")

    @channelrestrict.command(name="settings")
    async def cr_settings(self, ctx: commands.Context):
        """Show the current configuration."""
        conf = await self.config.guild(ctx.guild).all()
        channel = (
            ctx.guild.get_channel(conf["channel_id"]) if conf["channel_id"] else None
        )
        roles = []
        for rid in conf["whitelist_roles"]:
            role = ctx.guild.get_role(rid)
            if role:
                roles.append(role.mention)

        embed = discord.Embed(
            title="Channel Restrict Settings", color=await ctx.embed_color()
        )
        embed.add_field(name="Enabled", value=str(conf["enabled"]))
        embed.add_field(
            name="Allowed Channel", value=channel.mention if channel else "Not set"
        )
        embed.add_field(
            name="Whitelisted Roles",
            value=", ".join(roles) if roles else "None",
            inline=False,
        )
        await ctx.send(embed=embed)

    # ---------------------------------------------------------------
    # Helper
    # ---------------------------------------------------------------

    def _has_whitelisted_role(self, member: discord.Member, role_ids: list) -> bool:
        if not role_ids:
            return False
        member_role_ids = {r.id for r in member.roles}
        return bool(member_role_ids.intersection(role_ids))

    # ---------------------------------------------------------------
    # Global check for prefix commands
    # ---------------------------------------------------------------

    async def bot_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return True

        # Allow the config commands themselves to always work so admins
        # aren't locked out of fixing the setup.
        if ctx.command and ctx.command.qualified_name.startswith("channelrestrict"):
            return True

        conf = await self.config.guild(ctx.guild).all()
        if not conf["enabled"] or not conf["channel_id"]:
            return True

        if ctx.channel.id == conf["channel_id"]:
            return True

        if isinstance(ctx.author, discord.Member) and self._has_whitelisted_role(
            ctx.author, conf["whitelist_roles"]
        ):
            return True

        # Block, and notify the user.
        # Red can run global checks more than once for a single invocation
        # (e.g. once for the command, once for help-related checks), so
        # dedupe to avoid sending the notice multiple times.
        key = (ctx.author.id, ctx.channel.id)
        now = time.monotonic()
        last = self._recent_notices.get(key, 0)
        if now - last < 5:
            return False
        self._recent_notices[key] = now

        channel = ctx.guild.get_channel(conf["channel_id"])
        location = channel.mention if channel else "the designated bot channel"
        notice = f"{ctx.author.mention} You can't use bot commands here. Please head to {location}."

        try:
            msg = await ctx.send(notice, delete_after=10)
            try:
                await ctx.message.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass
        except discord.Forbidden:
            pass

        return False

    # ---------------------------------------------------------------
    # Slash / app command interception (true ephemeral response)
    # ---------------------------------------------------------------

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.application_command:
            return
        if interaction.guild is None:
            return

        conf = await self.config.guild(interaction.guild).all()
        if not conf["enabled"] or not conf["channel_id"]:
            return

        if interaction.channel_id == conf["channel_id"]:
            return

        member = interaction.user
        if isinstance(member, discord.Member) and self._has_whitelisted_role(
            member, conf["whitelist_roles"]
        ):
            return

        channel = interaction.guild.get_channel(conf["channel_id"])
        location = channel.mention if channel else "the designated bot channel"

        try:
            await interaction.response.send_message(
                f"You can't use bot commands here. Please head to {location}.",
                ephemeral=True,
            )
        except (discord.InteractionResponded, discord.HTTPException):
            pass
