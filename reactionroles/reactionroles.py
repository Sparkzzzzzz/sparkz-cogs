import discord
import re
from redbot.core import commands, Config
from redbot.core.bot import Red

HEX_REGEX = re.compile(r"^#?[0-9a-fA-F]{6}$")


class RRView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)


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
        panel = await cog.get_panel(self.guild_id, self.message_id)

        role = interaction.guild.get_role(self.role_id)
        member = interaction.user

        if not role:
            return await interaction.response.send_message(
                "Role not found.", ephemeral=True
            )

        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "I cannot manage that role.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        if panel.get("unique"):
            for rid in panel["roles"]:
                r = interaction.guild.get_role(int(rid))
                if r and r in member.roles and r.id != role.id:
                    await member.remove_roles(r)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.followup.send(f"Removed {role.name}", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.followup.send(f"Added {role.name}", ephemeral=True)


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
    # REACTION LISTENERS
    # =====================================================

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.member is None or payload.member.bot:
            return

        panel = await self.get_panel(payload.guild_id, payload.message_id)
        if not panel or panel["mode"] != "react":
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = payload.member

        emoji_str = str(payload.emoji)

        for rid, data in panel["roles"].items():
            if data["emoji"] == emoji_str:
                role = guild.get_role(int(rid))
                if not role or role >= guild.me.top_role:
                    return

                if panel.get("unique"):
                    for other_id in panel["roles"]:
                        r = guild.get_role(int(other_id))
                        if r and r in member.roles and r.id != role.id:
                            await member.remove_roles(r)

                await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        panel = await self.get_panel(payload.guild_id, payload.message_id)
        if not panel or panel["mode"] != "react":
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        emoji_str = str(payload.emoji)

        for rid, data in panel["roles"].items():
            if data["emoji"] == emoji_str:
                role = guild.get_role(int(rid))
                if role and role in member.roles:
                    await member.remove_roles(role)

    # =====================================================
    # GROUP
    # =====================================================

    @commands.group(name="rr", invoke_without_command=True)
    @commands.guild_only()
    async def rr(self, ctx):
        await ctx.send_help(ctx.command)

    # =====================================================
    # MAKE
    # =====================================================

    @rr.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def make(self, ctx):

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        await ctx.send("Reaction Role Setup Started. Type `cancel` anytime.")

        # Channel
        await ctx.send("Mention channel.")
        while True:
            msg = await self.bot.wait_for("message", check=check)
            if msg.content.lower() == "cancel":
                return await ctx.send("Cancelled.")
            if msg.channel_mentions:
                channel = msg.channel_mentions[0]
                break
            await ctx.send("Mention valid channel.")

        # Title/Desc
        await ctx.send("Send `Title | Description`")
        while True:
            msg = await self.bot.wait_for("message", check=check)
            if "|" in msg.content:
                title, description = [x.strip() for x in msg.content.split("|", 1)]
                break
            await ctx.send("Invalid format.")

        # Color
        await ctx.send("Send hex color or `none`")
        while True:
            msg = await self.bot.wait_for("message", check=check)
            if msg.content.lower() == "none":
                color = discord.Color.blurple()
                break
            if HEX_REGEX.match(msg.content):
                color = discord.Color(int(msg.content.replace("#", ""), 16))
                break
            await ctx.send("Invalid hex.")

        # Mode
        await ctx.send("Type: button / dropdown / react")
        while True:
            msg = await self.bot.wait_for("message", check=check)
            mode = msg.content.lower()
            if mode in ["button", "dropdown", "react"]:
                break

        unique = False
        if mode in ["button", "dropdown", "react"]:
            await ctx.send("Unique mode? (yes/no)")
            while True:
                msg = await self.bot.wait_for("message", check=check)
                if msg.content.lower() in ["yes", "y"]:
                    unique = True
                    break
                if msg.content.lower() in ["no", "n"]:
                    break

        # Roles
        roles = {}
        await ctx.send("Add roles: `emoji @Role` then type `done`")
        while True:
            msg = await self.bot.wait_for("message", check=check)

            if msg.content.lower() == "done":
                if roles:
                    break
                await ctx.send("Add at least one role.")
                continue

            if not msg.role_mentions:
                continue

            emoji = msg.content.split()[0]
            role = msg.role_mentions[0]

            roles[str(role.id)] = {
                "emoji": emoji,
                "label": role.name,
            }

            await msg.add_reaction("✅")

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
                custom_id=f"rr_select_{guild_id}_{message_id}",
            )

            async def callback(interaction: discord.Interaction):
                role_id = int(interaction.data["values"][0])
                role = interaction.guild.get_role(role_id)
                member = interaction.user

                await interaction.response.defer(ephemeral=True)

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

                new_view = await self.build_view(guild_id, message_id, panel)
                await interaction.message.edit(view=new_view)

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
        for mid, data in panels.items():
            channel = ctx.guild.get_channel(data["channel"])
            lines.append(
                f"ID: `{mid}` | Channel: {channel.mention if channel else 'Unknown'} | Mode: {data['mode']} | Unique: {data.get('unique', False)}"
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

            panel = panels[str(message_id)]
            channel = ctx.guild.get_channel(panel["channel"])

            if channel:
                try:
                    msg = await channel.fetch_message(message_id)
                    await msg.delete()
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    return await ctx.send("I cannot delete that message.")

            del panels[str(message_id)]

        await ctx.send("Panel deleted and message removed.")

