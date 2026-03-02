import discord
import re
from redbot.core import commands, Config
from redbot.core.bot import Red

HEX_REGEX = re.compile(r"^#?[0-9a-fA-F]{6}$")


# ==========================================
# VIEW CLASS
# ==========================================


class RRView(discord.ui.View):
    def __init__(self, cog, guild_id, message_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.message_id = message_id

    async def interaction_check(self, interaction: discord.Interaction):
        return True

    async def handle_role(self, interaction, role_id: int):
        guild = interaction.guild
        member = interaction.user
        role = guild.get_role(role_id)

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


# ==========================================
# MAIN COG
# ==========================================


class ReactionRoles(commands.Cog):
    """Advanced Reaction Roles (Buttons / Dropdown / React)"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1122334455)
        self.config.register_guild(messages={})

    async def cog_load(self):
        # Re-attach persistent views on restart
        for guild in self.bot.guilds:
            data = await self.config.guild(guild).messages()
            for message_id, rr_data in data.items():
                if rr_data["mode"] in ["button", "dropdown"]:
                    view = await self.build_view(guild.id, int(message_id), rr_data)
                    self.bot.add_view(view)

    # ======================================
    # GROUP
    # ======================================

    @commands.group()
    @commands.guild_only()
    async def rr(self, ctx):
        pass

    # ======================================
    # MAKE
    # ======================================

    @rr.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def make(self, ctx):

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        await ctx.send("Which channel?")
        msg = await self.bot.wait_for("message", check=check)
        if msg.content.lower() == "cancel":
            return await ctx.send("Cancelled.")

        if not msg.channel_mentions:
            return await ctx.send("Mention a channel.")

        channel = msg.channel_mentions[0]

        await ctx.send("Send `Title | Description`")
        msg = await self.bot.wait_for("message", check=check)
        if "|" not in msg.content:
            return await ctx.send("Invalid format.")

        title, description = [x.strip() for x in msg.content.split("|", 1)]

        await ctx.send("Hex color or `none`?")
        msg = await self.bot.wait_for("message", check=check)

        if msg.content.lower() == "none":
            color = discord.Color.blurple()
        else:
            if not HEX_REGEX.match(msg.content):
                return await ctx.send("Invalid hex.")
            color = discord.Color(int(msg.content.replace("#", ""), 16))

        await ctx.send("Select mode: `button`, `react`, or `dropdown`")
        msg = await self.bot.wait_for("message", check=check)
        mode = msg.content.lower()

        if mode not in ["button", "react", "dropdown"]:
            return await ctx.send("Invalid mode.")

        await ctx.send("Add roles using `emoji role_name` — type `done` when finished")

        roles = {}

        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "done":
                break

            parts = msg.content.split()
            if len(parts) < 2:
                await ctx.send("Invalid format.")
                continue

            emoji = parts[0]
            role_name = " ".join(parts[1:])

            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role:
                await ctx.send("Role not found.")
                continue

            roles[str(role.id)] = {"emoji": emoji, "label": role.name}

            await ctx.send(f"Linked {emoji} → {role.name}")

        embed = discord.Embed(title=title, description=description, color=color)

        message = await channel.send(embed=embed)

        # REACT MODE
        if mode == "react":
            for role_id, data in roles.items():
                await message.add_reaction(data["emoji"])

        # BUTTON / DROPDOWN MODE
        if mode in ["button", "dropdown"]:
            rr_data = {"roles": roles, "mode": mode}
            view = await self.build_view(ctx.guild.id, message.id, rr_data)
            await message.edit(view=view)
            self.bot.add_view(view)

        async with self.config.guild(ctx.guild).messages() as messages:
            messages[str(message.id)] = {
                "channel": channel.id,
                "title": title,
                "description": description,
                "color": color.value,
                "mode": mode,
                "roles": roles,
            }

        await ctx.send("Reaction role panel created.")

    # ======================================
    # BUILD VIEW
    # ======================================

    async def build_view(self, guild_id, message_id, rr_data):
        view = RRView(self, guild_id, message_id)

        roles = rr_data["roles"]
        mode = rr_data["mode"]

        if mode == "button":
            for role_id, data in roles.items():
                button = discord.ui.Button(
                    label=data["label"],
                    emoji=data["emoji"],
                    style=discord.ButtonStyle.secondary,
                )

                async def callback(interaction, r_id=int(role_id)):
                    await view.handle_role(interaction, r_id)

                button.callback = callback
                view.add_item(button)

        elif mode == "dropdown":
            options = []
            for role_id, data in roles.items():
                options.append(
                    discord.SelectOption(
                        label=data["label"], emoji=data["emoji"], value=role_id
                    )
                )

            select = discord.ui.Select(
                placeholder="Select your role",
                options=options,
                min_values=1,
                max_values=1,
            )

            async def select_callback(interaction):
                for value in select.values:
                    await view.handle_role(interaction, int(value))

            select.callback = select_callback
            view.add_item(select)

        return view

    # ======================================
    # REACTION LISTENER
    # ======================================

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

    # ======================================
    # DELETE
    # ======================================

    @rr.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def delete(self, ctx, message_id: int):
        async with self.config.guild(ctx.guild).messages() as messages:
            if str(message_id) not in messages:
                return await ctx.send("Not found.")
            del messages[str(message_id)]

        await ctx.send("Reaction role panel deleted from config.")
