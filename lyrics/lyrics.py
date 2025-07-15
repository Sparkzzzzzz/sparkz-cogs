import discord
from redbot.core import commands, Config
import aiohttp
import urllib.parse

class Lyrics(commands.Cog):
    """Get lyrics of songs."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=910182903182, force_registration=True)
        self.config.register_global(genius_token=None)

    @commands.command()
    async def setgenius(self, ctx, token: str):
        """Set Genius API token."""
        await self.config.genius_token.set(token)
        await ctx.send("✅ Genius API token set.")

    @commands.command(aliases=["lyric"])
    async def lyrics(self, ctx, *, song: str = None):
        """Fetch lyrics for the current or provided song."""
        genius_token = await self.config.genius_token()
        if not genius_token:
            return await ctx.send("⚠️ Genius token not set. Use `.setgenius <token>` first.")

        # If no song provided, try to get currently playing one
        if not song:
            player = ctx.bot.get_cog("Audio").get_player(ctx.guild)
            if not player or not player.current:
                return await ctx.send("❌ No song playing, and no song name provided.")
            song = player.current.title

        # Search Genius
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {genius_token}"}
            query = urllib.parse.quote(song)
            async with session.get(f"https://api.genius.com/search?q={query}", headers=headers) as resp:
                data = await resp.json()

        try:
            hits = data["response"]["hits"]
            if not hits:
                raise ValueError("No results")
            url = hits[0]["result"]["url"]
        except Exception:
            return await ctx.send("❌ Could not find lyrics for that song.")

        await ctx.send(f"🎶 Lyrics for **{song}**:\n<{url}>")
