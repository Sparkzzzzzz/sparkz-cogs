import discord
from redbot.core import commands, app_commands
from redbot.core.utils.chat_formatting import pagify
import aiohttp
import urllib.parse

GENIUS_API_BASE = "https://api.genius.com"

class Lyrics(commands.Cog):
    """Get song lyrics using the Genius API."""

    def __init__(self, bot):
        self.bot = bot
        self.api_token = "YOUR_GENIUS_API_TOKEN"  # Replace with your token or set via config later

    async def search_genius(self, query):
        headers = {"Authorization": f"Bearer {self.api_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GENIUS_API_BASE}/search?q={urllib.parse.quote(query)}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["response"]["hits"]
        return None

    async def get_lyrics_from_url(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # Naive scrape — this is prone to break if Genius changes layout
                    import re
                    match = re.search(r'<div class="lyrics">.*?<p>(.*?)</p>', html, re.DOTALL)
                    if match:
                        return re.sub(r'<.*?>', '', match.group(1)).strip()
        return None

    @commands.command()
    async def lyrics(self, ctx: commands.Context, *, song: str = None):
        """Fetch song lyrics from Genius. If no song is provided, it tries the currently playing one."""
        if song is None:
            audio_cog = self.bot.get_cog("Audio")
            if audio_cog is None:
                return await ctx.send("❌ Audio cog not loaded.")

            try:
                song = await audio_cog.get_api_info(ctx.guild.id, "title")
            except Exception:
                return await ctx.send("❌ Could not get the current song from Audio cog.")

        results = await self.search_genius(song)
        if not results:
            return await ctx.send("❌ No lyrics found.")

        best = results[0]["result"]
        title = best["full_title"]
        url = best["url"]

        lyrics = await self.get_lyrics_from_url(url)
        if not lyrics:
            return await ctx.send(f"Lyrics page: <{url}>\n❌ Couldn't extract lyrics, check the site manually.")

        pages = list(pagify(lyrics, page_length=1900))

        for i, page in enumerate(pages):
            embed = discord.Embed(title=title, description=page, url=url, color=discord.Color.green())
            embed.set_footer(text=f"Page {i+1}/{len(pages)}")
            await ctx.send(embed=embed)