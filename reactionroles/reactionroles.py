import discord
import re
from redbot.core import commands, Config
from redbot.core.bot import Red

HEX_REGEX = re.compile(r"^#?[0-9a-fA-F]{6}$")


# =========================================================
# BUTTON
# =========================================================


class RRButton(discord.ui.Button):
    def __init__(self, guild_id: int, role_id: int, label: str, emoji: str):
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id=f"rr_btn_{guild_id}_{role_id}",
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        member = interaction.user
        role = guild.get_role(self.role_id)

        if not role:
            return await interaction.followup.send("Role not found.", ephemeral=True)

        if role >= guild.me.top_role:
            return await interaction.followup.send(
                "I cannot manage that role (it is above me).",
                ephemeral=True,
            )

        try:
            if role in member.roles:
                await member.remove_roles(role)
                await interaction.followup.send(
                    f"Removed {role.name}",
                    ephemeral=True,
                )
            else:
                await member.add_roles(role)
                await interaction.followup.send(
                    f"Added {role.name}",
                    ephemeral=True,
                )
        except discord.Forbidden:
            await interaction.followup.send(
                "Missing Manage Roles permission.",
                ephemeral=True,
            )


# =========================================================
# VIEW
# =========================================================


class RRView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)


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
                    view = self.build_view(guild, message_id, panel)
                    self.bot.add_view(view)

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

        await ctx.send(
            "**Reaction Role Setup Started**\n\n"
            "You can type `cancel` at any time to stop."
        )

        # ---------------- CHANNEL ----------------

        await ctx.send("1️⃣ Mention the channel where the panel should be sent.")

        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            if msg.channel_mentions:
                channel = msg.channel_mentions[0]
                break

            await ctx.send("Please mention a valid channel.")

        perms = channel.permissions_for(ctx.guild.me)
        if not perms.send_messages or not perms.embed_links:
            return await ctx.send("I cannot send embeds in that channel.")

        # ---------------- TITLE ----------------

        await ctx.send(
            "2️⃣ Send the panel as:\n`Title | Description`\nUse `{roles}` to auto-list roles."
        )

        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            if "|" in msg.content:
                title, description = [x.strip() for x in msg.content.split("|", 1)]
                break

            await ctx.send("Invalid format. Use `Title | Description`.")

        # ---------------- COLOR ----------------

        await ctx.send("3️⃣ Send a hex color (example: `#FF0000`) or `none`.")

        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            if msg.content.lower() == "none":
                color = discord.Color.blurple()
                break

            if HEX_REGEX.match(msg.content):
                color = discord.Color(int(msg.content.replace("#", ""), 16))
                break

            await ctx.send("Invalid hex code.")

        # ---------------- MODE ----------------

        await ctx.send(
            "4️⃣ Choose panel type:\n"
            "`button` — clickable buttons\n"
            "`dropdown` — select menu\n"
            "`react` — classic reactions"
        )

        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            mode = msg.content.lower()

            if mode in ["button", "dropdown", "react"]:
                break

            await ctx.send("Invalid option.")

        # ---------------- UNIQUE ----------------

        unique = False

        if mode in ["button", "dropdown"]:
            await ctx.send(
                "5️⃣ Should users only have ONE role from this panel? (yes/no)"
            )

            while True:
                msg = await self.bot.wait_for("message", check=check)

                if msg.content.lower() == "cancel":
                    return await ctx.send("Setup cancelled.")

                if msg.content.lower() in ["yes", "y"]:
                    unique = True
                    break
                if msg.content.lower() in ["no", "n"]:
                    break

                await ctx.send("Please answer yes or no.")

        # ---------------- ROLES ----------------

        roles = {}

        await ctx.send(
            "6️⃣ Add roles using:\n`emoji @Role`\n\n"
            "Example:\n🍆 @Sparkz's Bots\n\n"
            "Type `done` when finished."
        )

        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            if msg.content.lower() == "done":
                if roles:
                    break
                await ctx.send("Add at least one role.")
                continue

            if not msg.role_mentions:
                await ctx.send("You must mention a role.")
                continue

            parts = msg.content.split()
            if len(parts) < 2:
                await ctx.send("Invalid format.")
                continue

            emoji = parts[0]
            role = msg.role_mentions[0]

            roles[str(role.id)] = {
                "emoji": emoji,
                "label": role.name,
            }

            await msg.add_reaction("✅")

        # ---------------- BUILD EMBED ----------------

        if "{roles}" in description:
            role_lines = "\n".join(
                f"{data['emoji']} <@&{role_id}>" for role_id, data in roles.items()
            )
            description = description.replace("{roles}", role_lines)

        embed = discord.Embed(title=title, description=description, color=color)

        message = await channel.send(embed=embed)

        panel_data = {
            "mode": mode,
            "roles": roles,
            "unique": unique,
        }

        if mode == "react":
            for data in roles.values():
                await message.add_reaction(data["emoji"])

        if mode in ["button", "dropdown"]:
            view = self.build_view(ctx.guild, message.id, panel_data)
            await message.edit(view=view)
            self.bot.add_view(view)

        async with self.config.guild(ctx.guild).panels() as panels:
            panels[str(message.id)] = {
                "channel": channel.id,
                **panel_data,
            }

        await ctx.send(f"Panel created in {channel.mention} (ID: {message.id})")

    # =====================================================
    # BUILD VIEW
    # =====================================================

    def build_view(self, guild, message_id, panel):
        view = RRView()

        if panel["mode"] == "button":
            for role_id, data in panel["roles"].items():
                view.add_item(
                    RRButton(
                        guild.id,
                        int(role_id),
                        data["label"],
                        data["emoji"],
                    )
                )

        elif panel["mode"] == "dropdown":
            options = [
                discord.SelectOption(
                    label=data["label"],
                    emoji=data["emoji"],
                    value=role_id,
                )
                for role_id, data in panel["roles"].items()
            ]

            select = discord.ui.Select(
                placeholder="Select your role",
                options=options,
                min_values=1,
                max_values=1,
                custom_id=f"rr_select_{guild.id}_{message_id}",
            )

            async def callback(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)

                selected_role_id = int(select.values[0])
                selected_role = interaction.guild.get_role(selected_role_id)

                if not selected_role:
                    return await interaction.followup.send(
                        "Role not found.", ephemeral=True
                    )

                if selected_role >= interaction.guild.me.top_role:
                    return await interaction.followup.send(
                        "I cannot manage that role (it is above me).",
                        ephemeral=True,
                    )

                member = interaction.user

                # UNIQUE MODE
                if panel.get("unique"):
                    for role_id in panel["roles"]:
                        role = interaction.guild.get_role(int(role_id))
                        if role in member.roles and role.id != selected_role_id:
                            await member.remove_roles(role)

                if selected_role in member.roles:
                    await member.remove_roles(selected_role)
                    await interaction.followup.send(
                        f"Removed {selected_role.name}",
                        ephemeral=True,
                    )
                else:
                    await member.add_roles(selected_role)
                    await interaction.followup.send(
                        f"Added {selected_role.name}",
                        ephemeral=True,
                    )

            select.callback = callback
            view.add_item(select)

        return view

    # =====================================================
    # LIST
    # =====================================================

    @rr.command()
    async def list(self, ctx):
        panels = await self.config.guild(ctx.guild).panels()

        if not panels:
            return await ctx.send("No panels found.")

        lines = []
        for message_id, data in panels.items():
            channel = ctx.guild.get_channel(data["channel"])
            lines.append(
                f"• ID: `{message_id}` | Channel: {channel.mention if channel else 'Unknown'} | Mode: {data['mode']} | Unique: {data.get('unique', False)}"
            )

        await ctx.send("\n".join(lines))

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

        await ctx.send("Panel deleted from configuration.")
