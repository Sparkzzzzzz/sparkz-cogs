import discord
import re
from redbot.core import commands, Config
from redbot.core.bot import Red

HEX_REGEX = re.compile(r"^#?[0-9a-fA-F]{6}$")


# =========================================================
# VIEW
# =========================================================


class RRView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)


# =========================================================
# BUTTON
# =========================================================


class RRButton(discord.ui.Button):
    def __init__(
        self, guild_id: int, message_id: int, role_id: int, label: str, emoji: str
    ):
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id=f"rr_btn_{guild_id}_{message_id}_{role_id}",
        )
        self.guild_id = guild_id
        self.message_id = message_id
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("ReactionRoles")
        if not cog:
            return

        panel = await cog.get_panel(self.guild_id, self.message_id)
        if not panel:
            return await interaction.response.send_message(
                "Panel not found.", ephemeral=True
            )

        guild = interaction.guild
        member = interaction.user
        role = guild.get_role(self.role_id)

        if not role:
            return await interaction.response.send_message(
                "Role not found.", ephemeral=True
            )

        if role >= guild.me.top_role:
            return await interaction.response.send_message(
                "I cannot manage that role (it is above me).",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        try:
            # UNIQUE MODE
            if panel.get("unique"):
                for rid in panel["roles"]:
                    r = guild.get_role(int(rid))
                    if r in member.roles and r.id != role.id:
                        await member.remove_roles(r)

            if role in member.roles:
                await member.remove_roles(role)
                await interaction.followup.send(f"Removed {role.name}", ephemeral=True)
            else:
                await member.add_roles(role)
                await interaction.followup.send(f"Added {role.name}", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "Missing Manage Roles permission.",
                ephemeral=True,
            )


# =========================================================
# COG
# =========================================================


class ReactionRoles(commands.Cog):
    """Persistent Reaction Role Panels (Buttons / Dropdown / React)"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7788990011)
        self.config.register_guild(panels={})

    async def cog_load(self):
        all_data = await self.config.all_guilds()

        for guild_id, data in all_data.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            for message_id, panel in data.get("panels", {}).items():
                if panel["mode"] in ["button", "dropdown"]:
                    view = await self.build_view(guild_id, int(message_id), panel)
                    self.bot.add_view(view)

    async def get_panel(self, guild_id: int, message_id: int):
        panels = await self.config.guild_from_id(guild_id).panels()
        return panels.get(str(message_id))

    # =====================================================
    # GROUP
    # =====================================================

    @commands.group(name="rr", invoke_without_command=True)
    @commands.guild_only()
    async def rr(self, ctx):
        pass

    # =====================================================
    # MAKE
    # =====================================================

    @rr.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def make(self, ctx):

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        await ctx.send("**Reaction Role Setup Started**\nType `cancel` anytime.")

        # CHANNEL
        await ctx.send("Mention the channel for the panel.")
        while True:
            msg = await self.bot.wait_for("message", check=check)
            if msg.content.lower() == "cancel":
                return await ctx.send("Cancelled.")
            if msg.channel_mentions:
                channel = msg.channel_mentions[0]
                break
            await ctx.send("Mention a valid channel.")

        # TITLE/DESC
        await ctx.send("Send as: `Title | Description` (use {roles} to auto list)")
        while True:
            msg = await self.bot.wait_for("message", check=check)
            if msg.content.lower() == "cancel":
                return await ctx.send("Cancelled.")
            if "|" in msg.content:
                title, description = [x.strip() for x in msg.content.split("|", 1)]
                break
            await ctx.send("Invalid format.")

        # COLOR
        await ctx.send("Send hex color or `none`.")
        while True:
            msg = await self.bot.wait_for("message", check=check)
            if msg.content.lower() == "cancel":
                return await ctx.send("Cancelled.")
            if msg.content.lower() == "none":
                color = discord.Color.blurple()
                break
            if HEX_REGEX.match(msg.content):
                color = discord.Color(int(msg.content.replace("#", ""), 16))
                break
            await ctx.send("Invalid hex.")

        # MODE
        await ctx.send("Type: `button`, `dropdown`, or `react`")
        while True:
            msg = await self.bot.wait_for("message", check=check)
            mode = msg.content.lower()
            if mode in ["button", "dropdown", "react"]:
                break
            await ctx.send("Invalid option.")

        unique = False
        if mode in ["button", "dropdown"]:
            await ctx.send("Unique mode? (yes/no)")
            while True:
                msg = await self.bot.wait_for("message", check=check)
                if msg.content.lower() in ["yes", "y"]:
                    unique = True
                    break
                if msg.content.lower() in ["no", "n"]:
                    break
                await ctx.send("Answer yes or no.")

        # ROLES
        roles = {}
        await ctx.send("Add roles using: `emoji @Role`\nType `done` when finished.")
        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "done":
                if roles:
                    break
                await ctx.send("Add at least one role.")
                continue

            if not msg.role_mentions:
                await ctx.send("Mention a role.")
                continue

            parts = msg.content.split()
            emoji = parts[0]
            role = msg.role_mentions[0]

            roles[str(role.id)] = {
                "emoji": emoji,
                "label": role.name,
            }

            await msg.add_reaction("✅")

        # Build embed
        if "{roles}" in description:
            role_lines = "\n".join(
                f"{data['emoji']} <@&{rid}>" for rid, data in roles.items()
            )
            description = description.replace("{roles}", role_lines)

        embed = discord.Embed(title=title, description=description, color=color)
        message = await channel.send(embed=embed)

        panel_data = {
            "mode": mode,
            "roles": roles,
            "unique": unique,
            "channel": channel.id,
        }

        if mode == "react":
            for data in roles.values():
                await message.add_reaction(data["emoji"])

        if mode in ["button", "dropdown"]:
            view = await self.build_view(ctx.guild.id, message.id, panel_data)
            await message.edit(view=view)
            self.bot.add_view(view)

        async with self.config.guild(ctx.guild).panels() as panels:
            panels[str(message.id)] = panel_data

        await ctx.message.add_reaction("✅")

    # =====================================================
    # BUILD VIEW
    # =====================================================

    async def build_view(self, guild_id: int, message_id: int, panel):
        view = RRView()

        if panel["mode"] == "button":
            for rid, data in panel["roles"].items():
                view.add_item(
                    RRButton(
                        guild_id,
                        message_id,
                        int(rid),
                        data["label"],
                        data["emoji"],
                    )
                )

        elif panel["mode"] == "dropdown":
            options = [
                discord.SelectOption(
                    label=data["label"],
                    emoji=data["emoji"],
                    value=rid,
                )
                for rid, data in panel["roles"].items()
            ]

            select = discord.ui.Select(
                placeholder="Select your role",
                options=options,
                min_values=1,
                max_values=1,
                custom_id=f"rr_select_{guild_id}_{message_id}",
            )

            async def callback(interaction: discord.Interaction):
                cog = interaction.client.get_cog("ReactionRoles")
                panel = await cog.get_panel(guild_id, message_id)

                role_id = int(select.values[0])
                role = interaction.guild.get_role(role_id)
                member = interaction.user

                await interaction.response.defer(ephemeral=True)

                if panel.get("unique"):
                    for rid in panel["roles"]:
                        r = interaction.guild.get_role(int(rid))
                        if r in member.roles and r.id != role_id:
                            await member.remove_roles(r)

                if role in member.roles:
                    await member.remove_roles(role)
                    await interaction.followup.send(
                        f"Removed {role.name}", ephemeral=True
                    )
                else:
                    await member.add_roles(role)
                    await interaction.followup.send(
                        f"Added {role.name}", ephemeral=True
                    )

                # CLEAR DROPDOWN VISUALLY
                new_view = await cog.build_view(guild_id, message_id, panel)
                await interaction.message.edit(view=new_view)

            select.callback = callback
            view.add_item(select)

        return view

    # =====================================================
    # DELETE
    # =====================================================

    @rr.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def delete(self, ctx, message_id: int):
        async with self.config.guild(ctx.guild).panels() as panels:
            if str(message_id) not in panels:
                return await ctx.send("Panel not found.")
            del panels[str(message_id)]

        await ctx.send("Panel deleted.")
