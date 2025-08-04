from redbot.core import commands, Config
from redbot.core.bot import Red
import discord


class CommandLockdown(commands.Cog):
    """Silently blocks all commands for users except the bot owner or those with a whitelisted role."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=987654321)
        self.config.register_guild(whitelist_roles=[])

    def is_whitelisted(self, member: discord.Member, whitelist_role_ids: list[int]):
        return any(role.id in whitelist_role_ids for role in member.roles)

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        if ctx.guild is None:
            return  # Ignore DMs

        if await self.bot.is_owner(ctx.author):
            return  # Bot owner always allowed

        whitelist_roles = await self.config.guild(ctx.guild).whitelist_roles()
        if self.is_whitelisted(ctx.author, whitelist_roles):
            return  # User has one of the whitelisted roles

        # Block all commands silently for everyone else
        raise commands.CheckFailure()

    @commands.guild_only()
    @commands.command()
    @commands.is_owner()
    async def allowrole(self, ctx: commands.Context, role: discord.Role):
        """Add a role to the command whitelist."""
        roles = await self.config.guild(ctx.guild).whitelist_roles()
        if role.id in roles:
            await ctx.send("⚠️ That role is already whitelisted.")
            return
        roles.append(role.id)
        await self.config.guild(ctx.guild).whitelist_roles.set(roles)
        await ctx.send(f"✅ Added `{role.name}` to whitelist.")

    @commands.guild_only()
    @commands.command()
    @commands.is_owner()
    async def removerole(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from the command whitelist."""
        roles = await self.config.guild(ctx.guild).whitelist_roles()
        if role.id not in roles:
            await ctx.send("⚠️ That role is not in the whitelist.")
            return
        roles.remove(role.id)
        await self.config.guild(ctx.guild).whitelist_roles.set(roles)
        await ctx.send(f"✅ Removed `{role.name}` from whitelist.")

    @commands.guild_only()
    @commands.command(name="listroles")
    @commands.is_owner()
    async def list_roles(self, ctx: commands.Context):
        """List currently whitelisted roles."""
        role_ids = await self.config.guild(ctx.guild).whitelist_roles()
        if not role_ids:
            await ctx.send("🚫 No roles are whitelisted.")
            return
        roles = [ctx.guild.get_role(rid) for rid in role_ids]
        role_names = [role.name for role in roles if role is not None]
        await ctx.send(
            "✅ Whitelisted roles:\n" + "\n".join(f"- `{name}`" for name in role_names)
        )
