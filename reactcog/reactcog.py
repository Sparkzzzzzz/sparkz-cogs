import discord
from redbot.core import commands, Config
from redbot.core.bot import Red

class ReactCog(commands.Cog):
    """
    Simple reaction cog that adds reactions to messages.
    Supports multiple reactions per message and persists across reloads.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=99283472934723)
        self.config.register_global(messages={})

    # ---------------------------------------------------
    # Utilities
    # ---------------------------------------------------
    async def _apply_reactions(self):
        """Reapply all stored reactions on cog load."""
        data = await self.config.messages()
        for msg_id, entry in data.items():
            channel_id = entry["channel"]
            emojis = entry["emojis"]

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue

            try:
                msg = await channel.fetch_message(int(msg_id))
            except Exception:
                continue

            for e in emojis:
                try:
                    await msg.add_reaction(e)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_ready(self):
        # Reapply reactions after bot starts
        await self._apply_reactions()

    # ---------------------------------------------------
    # Commands
    # ---------------------------------------------------

    @commands.group(name="react", invoke_without_command=True)
    @commands.is_owner()
    async def react_group(self, ctx):
        """Base command for reaction controls."""
        await ctx.send("Use `.react add`, `.react remove`, `.react list`")

    @react_group.command(name="add")
    @commands.is_owner()
    async def react_add(self, ctx, channel: discord.TextChannel, message_id: int, emoji: str):
        """
        Add a reaction to a message.
        Example: .react add #general 123456789012345678 👍
        """
        try:
            msg = await channel.fetch_message(message_id)
        except:
            return await ctx.send("❌ Unable to fetch that message.")

        try:
            await msg.add_reaction(emoji)
        except:
            return await ctx.send("❌ Could not add that reaction.")

        data = await self.config.messages()

        if str(message_id) not in data:
            data[str(message_id)] = {"channel": channel.id, "emojis": []}

        if emoji not in data[str(message_id)]["emojis"]:
            data[str(message_id)]["emojis"].append(emoji)

        await self.config.messages.set(data)

        await ctx.send(f"✅ Reaction `{emoji}` added to message `{message_id}`")

    @react_group.command(name="remove")
    @commands.is_owner()
    async def react_remove(self, ctx, message_id: int, emoji: str):
        """
        Remove a stored reaction from a message.
        Example: .react remove 123456789012345678 👍
        """
        data = await self.config.messages()

        if str(message_id) not in data:
            return await ctx.send("❌ That message has no stored reactions.")

        if emoji not in data[str(message_id)]["emojis"]:
            return await ctx.send("❌ That reaction is not stored for this message.")

        data[str(message_id)]["emojis"].remove(emoji)

        if not data[str(message_id)]["emojis"]:
            # If empty, remove the entry
            del data[str(message_id)]

        await self.config.messages.set(data)

        await ctx.send(f"🗑 Removed reaction `{emoji}` from `{message_id}`")

    @react_group.command(name="list")
    @commands.is_owner()
    async def react_list(self, ctx):
        """List all stored message reactions."""
        data = await self.config.messages()

        if not data:
            return await ctx.send("📭 No stored reactions.")

        lines = []
        for msg_id, entry in data.items():
            channel_id = entry["channel"]
            emojis = entry["emojis"]
            lines.append(f"📌 **Message `{msg_id}` in <#{channel_id}>** → {', '.join(emojis)}")

        await ctx.send("\n".join(lines))
