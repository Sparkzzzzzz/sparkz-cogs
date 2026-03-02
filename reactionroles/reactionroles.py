import discord
import re
from redbot.core import commands, Config
from redbot.core.bot import Red

HEX_REGEX = re.compile(r"^#?[0-9a-fA-F]{6}$")


# =========================================================
# VIEW
# =========================================================

class RRButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, emoji: str):
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id=f"rr_btn_{role_id}"
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        role = guild.get_role(self.role_id)

        if not role:
            return await interaction.response.send_message(
                "Role not found.", ephemeral=True
            )

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(
                f"Removed {role.name}", ephemeral=True
            )
        else:
            await member.add_roles(role)
            await interaction.response.send_message(
                f"Added {role.name}", ephemeral=True
            )


class RRView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)


# =========================================================
# COG
# =========================================================

class ReactionRoles(commands.Cog):
    """Stable Reaction Roles v2"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7788990011)
        self.config.register_guild(messages={})

    async def cog_load(self):
        # Re-attach persistent views
        for guild in self.bot.guilds:
            data = await self.config.guild(guild).messages()
            for message_id, rr_data in data.items():
                if rr_data["mode"] in ["button", "dropdown"]:
                    view = await self.build_view(rr_data)
                    self.bot.add_view(view)

    # =====================================================
    # GROUP
    # =====================================================

    @commands.group(name="rr")
    @commands.guild_only()
    async def rr(self, ctx):
        """Reaction role commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Subcommands: make, delete")

    # =====================================================
    # MAKE (STABLE WIZARD)
    # =====================================================

    @rr.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def make(self, ctx):

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        # ---------------- CHANNEL ----------------

        while True:
            await ctx.send(
                "Which channel should the panel be sent in?\n"
                "Mention it. Type `cancel` to exit."
            )

            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            if msg.channel_mentions:
                channel = msg.channel_mentions[0]
                break

            await ctx.send("Invalid channel. Please mention a channel.")

        # Permission check
        perms = channel.permissions_for(ctx.guild.me)
        if not perms.send_messages or not perms.embed_links:
            return await ctx.send("I lack permission to send embeds there.")

        # ---------------- TITLE / DESCRIPTION ----------------

        while True:
            await ctx.send(
                "Send the message as:\n"
                "`Title | Description`\n"
                "Use `{roles}` to auto-insert role list.\n"
                "Type `cancel` to exit."
            )

            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            if "|" in msg.content:
                title, description = [
                    x.strip() for x in msg.content.split("|", 1)
                ]
                break

            await ctx.send("Invalid format. Use `Title | Description`.")

        # ---------------- COLOR ----------------

        while True:
            await ctx.send(
                "Send hex color (example: #FF0000) or `none`.\n"
                "Type `cancel` to exit."
            )

            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            if msg.content.lower() == "none":
                color = discord.Color.blurple()
                break

            if HEX_REGEX.match(msg.content):
                color = discord.Color(int(msg.content.replace("#", ""), 16))
                break

            await ctx.send("Invalid hex code. Try again.")

        # ---------------- MODE ----------------

        while True:
            await ctx.send(
                "Select mode:\n"
                "`button` — clickable buttons\n"
                "`dropdown` — select menu\n"
                "`react` — classic reactions\n"
                "Type `cancel` to exit."
            )

            msg = await self.bot.wait_for("message", check=check)
            mode = msg.content.lower()

            if mode == "cancel":
                return await ctx.send("Setup cancelled.")

            if mode in ["button", "dropdown", "react"]:
                break

            await ctx.send("Invalid mode.")

        # ---------------- ROLE COLLECTION ----------------

        roles = {}

        await ctx.send(
            "Now add roles in this format:\n"
            "`emoji @Role`\n\n"
            "Example:\n"
            "🍆 @Sparkz's Bots\n\n"
            "Type `done` when finished."
        )

        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "cancel":
                return await ctx.send("Setup cancelled.")

            if msg.content.lower() == "done":
                if not roles:
                    await ctx.send("You must add at least one role.")
                    continue
                break

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
                "label": role.name
            }

            await ctx.send(f"Linked {emoji} → {role.name}")

        # ---------------- BUILD EMBED ----------------

        if "{roles}" in description:
            role_lines = "\n".join(
                f"{data['emoji']} <@&{role_id}>"
                for role_id, data in roles.items()
            )
            description = description.replace("{roles}", role_lines)

        embed = discord.Embed(title=title, description=description, color=color)

        await ctx.send("Creating panel...")

        message = await channel.send(embed=embed)

        # ---------------- APPLY MODE ----------------

        if mode == "react":
            for role_id, data in roles.items():
                await message.add_reaction(data["emoji"])

        if mode in ["button", "dropdown"]:
            rr_data = {
                "roles": roles,
                "mode": mode
            }

            view = await self.build_view(rr_data)
            await message.edit(view=view)
            self.bot.add_view(view)

        # Save config
        async with self.config.guild(ctx.guild).messages() as messages:
            messages[str(message.id)] = {
                "channel": channel.id,
                "title": title,
                "description": description,
                "color": color.value,
                "mode": mode,
                "roles": roles
            }

        await ctx.send(f"Panel created in {channel.mention}.")

    # =====================================================
    # BUILD VIEW
    # =====================================================

    async def build_view(self, rr_data):
        view = RRView()

        if rr_data["mode"] == "button":
            for role_id, data in rr_data["roles"].items():
                view.add_item(
                    RRButton(
                        role_id=int(role_id),
                        label=data["label"],
                        emoji=data["emoji"]
                    )
                )

        elif rr_data["mode"] == "dropdown":
            options = [
                discord.SelectOption(
                    label=data["label"],
                    emoji=data["emoji"],
                    value=role_id
                )
                for role_id, data in rr_data["roles"].items()
            ]

            select = discord.ui.Select(
                placeholder="Select your role",
                options=options,
                min_values=1,
                max_values=1
            )

            async def select_callback(interaction):
                for value in select.values:
                    role = interaction.guild.get_role(int(value))
                    if role in interaction.user.roles:
                        await interaction.user.remove_roles(role)
                        await interaction.response.send_message(
                            f"Removed {role.name}", ephemeral=True
                        )
                    else:
                        await interaction.user.add_roles(role)
                        await interaction.response.send_message(
                            f"Added {role.name}", ephemeral=True
                        )

            select.callback = select_callback
            view.add_item(select)

        return view

    # =====================================================
    # REACT LISTENER
    # =====================================================

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)

        if not member or member.bot:
            return

        data = await self.config.guild(guild).messages()
        if str(payload.message_id) not in data:
            return

        rr_data = data[str(payload.message_id)]
        if rr_data["mode"] != "react":
            return

        emoji = str(payload.emoji)

        for role_id, info in rr_data["roles"].items():
            if info["emoji"] == emoji:
                role = guild.get_role(int(role_id))
                if role:
                    await member.add_roles(role)

    # =====================================================
    # DELETE
    # =====================================================

    @rr.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def delete(self, ctx, message_id: int):
        async with self.config.guild(ctx.guild).messages() as messages:
            if str(message_id) not in messages:
                return await ctx.send("Panel not found.")
            del messages[str(message_id)]

        await ctx.send("Panel configuration deleted.")
