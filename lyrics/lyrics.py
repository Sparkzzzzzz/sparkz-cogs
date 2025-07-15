import discord
from redbot.core import commands
import aiohttp
from redbot.core.utils.chat_formatting import pagify

GENIUS_API_URL = "https://api.genius.com"

class Lyrics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token = None

    @commands.command()
    @commands.is_owner()
    async def setgeniustoken(self, ctx, token: str):
        """Set Genius API token. (Hidden, secure)"""
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass  # Message might already be gone or missing permissions

        self.token = token
        try:
            await ctx.message.add_reaction("✅")
        except discord.HTTPException:
            await ctx.send("✅ Token set securely.", delete_after=5)


    async def get_current_song_title(self, ctx):
        audio = self.bot.get_cog("Audio")
        if not audio:
            return None

        # Accessing internal Audio state (works for Red 3.5.20, Audio 2.5.0)
        states = getattr(audio, "_guild_states", {})
        state = states.get(ctx.guild.id)
        if not state:
            return None

        current = getattr(state, "current", None)
        if not current:
            return None

        return getattr(current, "title", None)

    async def get_lyrics(self, title):
        if not self.token:
            return None, "❌ Genius token not set. Use `.setgeniustoken <token>`"
        headers = {"Authorization": f"Bearer {self.token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GENIUS_API_URL}/search?q={title}", headers=headers) as resp:
                data = await resp.json()
                if not data["response"]["hits"]:
                    return None, "❌ No results found."

                song_path = data["response"]["hits"][0]["result"]["path"]
                song_url = f"https://genius.com{song_path}"
                async with session.get(song_url) as page:
                    html = await page.text()

        import re
        match = re.findall(r'<div data-lyrics-container="true">(.*?)</div>', html, re.DOTALL)
        if not match:
            return None, "❌ Could not extract lyrics."

        clean = re.sub(r"<.*?>", "", "".join(match)).strip()
        return clean, None

    @commands.command()
    async def lyrics(self, ctx):
        """Get lyrics for the current song."""
        title = await self.get_current_song_title(ctx)
        if not title:
            return await ctx.send("❌ Could not get the current song from Audio cog.")

        await ctx.send(f"🔎 Searching Genius for `{title}`...")
        lyrics, error = await self.get_lyrics(title)

        if error:
            return await ctx.send(error)

        for page in pagify(lyrics, page_length=2000):
            await ctx.send(page)

    @commands.command()
    async def debugaudio(self, ctx):
        """Debug Audio state."""
        audio = self.bot.get_cog("Audio")
        if not audio:
            return await ctx.send("❌ Audio cog not found.")

        states = getattr(audio, "_guild_states", {})
        state = states.get(ctx.guild.id)
        if not state:
            return await ctx.send("❌ No state found for this guild.")

        current = getattr(state, "current", None)
        if not current:
            return await ctx.send("❌ No track currently playing.")

        return await ctx.send(f"🎵 Currently playing: `{getattr(current, 'title', 'Unknown')}`")
