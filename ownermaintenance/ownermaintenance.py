import discord
from discord.ext import commands
import json
import os

CONFIG_FILE = "ownermaintenance.json"


class OwnerMaintainace(commands.Cog):
    """Global Owner Maintenance Mode with exceptions"""

    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_config()
        if "maintenance_enabled" not in self.data:
            self.data["maintenance_enabled"] = False
        if "exceptions" not in self.data:
            self.data["exceptions"] = (
                {}
            )  # {id: {"type":"user"/"role"/"guild","cogs":["all"]}}
        self.save_config()
        self.bot.add_listener(self._check_maintenance, "on_message")

    # ---------------- Config ---------------- #
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    # ---------------- Maintenance Check ---------------- #
    async def _check_maintenance(self, message):
        if message.author.bot:
            return
        if not self.data.get("maintenance_enabled", False):
            return

        # Owners bypass maintenance
        app_info = await self.bot.application_info()
        if message.author.id == app_info.owner.id:
            return

        # Determine IDs for exception check
        user_id = str(message.author.id)
        role_ids = {str(r.id) for r in getattr(message.author, "roles", [])}
        guild_id = str(message.guild.id) if message.guild else None

        # Check exceptions
        for eid, info in self.data.get("exceptions", {}).items():
            if eid in {user_id, guild_id} or eid in role_ids:
                # exception found
                return

        # Send maintenance embed
        try:
            await message.channel.send(
                embed=discord.Embed(
                    title="🛠️ Bot Under Maintenance",
                    description="The bot is currently under maintenance. Please try again later.",
                    color=discord.Color.red(),
                ),
                delete_after=5,
            )
        except discord.Forbidden:
            pass
        try:
            await message.delete(delay=1)
        except discord.Forbidden:
            pass

    # ---------------- Commands ---------------- #
    @commands.group(name="om", invoke_without_command=True)
    @commands.is_owner()
    async def om(self, ctx):
        """Owner Maintenance management commands"""
        await ctx.send(
            "Commands:\n"
            "`om toggle` — Toggle global maintenance\n"
            "`om set allow/deny <id>` — Add/remove exceptions\n"
            "`om list` — List all exceptions"
        )

    @om.command(name="toggle")
    @commands.is_owner()
    async def toggle(self, ctx):
        self.data["maintenance_enabled"] = not self.data.get(
            "maintenance_enabled", False
        )
        self.save_config()
        await ctx.send(
            f"🛠️ Maintenance mode is now {'ON' if self.data['maintenance_enabled'] else 'OFF'}"
        )

    @om.command(name="set")
    @commands.is_owner()
    async def set_exception(self, ctx, mode: str, target_id: str):
        """Add or remove an exception. Target can be user/role/server ID or mention"""
        mode = mode.lower()
        if mode not in {"allow", "deny"}:
            return await ctx.send("❌ Mode must be `allow` or `deny`.")

        obj_type = None
        obj_id = None

        # Resolve ID
        if target_id.isdigit():
            obj_id = int(target_id)
            # Guess type
            if ctx.guild and ctx.guild.get_member(obj_id):
                obj_type = "user"
            elif ctx.guild and ctx.guild.get_role(obj_id):
                obj_type = "role"
            elif self.bot.get_guild(obj_id):
                obj_type = "guild"
            else:
                obj_type = "unknown"
        elif target_id.startswith("<@") and target_id.endswith(">"):
            obj_type = "user"
            obj_id = int(target_id.strip("<@!>"))
        elif target_id.startswith("<@&") and target_id.endswith(">"):
            obj_type = "role"
            obj_id = int(target_id.strip("<@&>"))
        else:
            return await ctx.send("❌ Could not resolve target. Use ID or mention.")

        key = str(obj_id)

        if mode == "deny":
            if key in self.data["exceptions"]:
                self.data["exceptions"].pop(key)
                self.save_config()
                return await ctx.send(
                    f"❌ Removed {obj_type} `{obj_id}` from exceptions"
                )
            return await ctx.send("❌ That target is not in exceptions")

        # allow
        self.data["exceptions"][key] = {"type": obj_type, "cogs": ["all"]}
        self.save_config()
        await ctx.send(f"✅ {obj_type.capitalize()} `{obj_id}` allowed (exception)")

    @om.command(name="list")
    @commands.is_owner()
    async def list_exceptions(self, ctx):
        exceptions = self.data.get("exceptions", {})
        if not exceptions:
            return await ctx.send("No exceptions set.")

        lines = []
        for eid, info in exceptions.items():
            lines.append(f"{info['type'].capitalize()} `{eid}` → All commands")

        await ctx.send("🛠️ **Maintenance Exceptions:**\n" + "\n".join(lines))


async def setup(bot):
    await bot.add_cog(OwnerMaintainace(bot))
