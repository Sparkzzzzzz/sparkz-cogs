from redbot.core import commands, bot
import discord

class ForcePresence(commands.Cog):
    def __init__(self, bot: bot.Red):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # reapply your configured presence
        presence = await self.bot.get_presence()

        # presence is a dict: {"type": "playing", "name": "something"}
        if presence:
            activity_type = presence.get("type", "playing")
            name = presence.get("name", "")

            discord_activity = {
                "playing": discord.Game(name),
                "listening": discord.Activity(type=discord.ActivityType.listening, name=name),
                "watching": discord.Activity(type=discord.ActivityType.watching, name=name),
            }.get(activity_type, discord.Game(name))

            await self.bot.change_presence(
                activity=discord_activity,
                status=discord.Status.online
            )

        # optional logging
        print("Presence reapplied on reconnect.")
