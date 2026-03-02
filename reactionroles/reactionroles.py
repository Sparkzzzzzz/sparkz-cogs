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
                    if r and r in member.roles and r.id != role.id:
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
    """Persistent Reaction Role Panels"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7788990011)
        self.config.register_guild(panels={})

    async def cog_load(self):
        all_data = await self.config.all_guilds()

        for guild_id, data in all_data.items():
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

                if not panel:
                    return await interaction.response.send_message(
                        "Panel missing.", ephemeral=True
                    )

                role_id = int(interaction.data["values"][0])
                role = interaction.guild.get_role(role_id)
                member = interaction.user

                if not role:
                    return await interaction.response.send_message(
                        "Role not found.", ephemeral=True
                    )

                if role >= interaction.guild.me.top_role:
                    return await interaction.response.send_message(
                        "I cannot manage that role.",
                        ephemeral=True,
                    )

                await interaction.response.defer(ephemeral=True)

                # UNIQUE MODE
                if panel.get("unique"):
                    for rid in panel["roles"]:
                        r = interaction.guild.get_role(int(rid))
                        if r and r in member.roles and r.id != role_id:
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
