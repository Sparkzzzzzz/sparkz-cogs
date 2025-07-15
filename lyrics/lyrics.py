import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import pagify
import aiohttp
import urllib.parse
import re

class Lyrics(commands.Cog):
    """Get song lyrics using Genius."""

    def __init__(self, bot):
        self.bot = bot
        self.api_token = "K5BsSazUWSUteWTFI7_Fsyd2RE7KF2RypVrKhstRdFOVfUOMdLXYFaSEotvhL2tg"  # Replace this with your Genius token

    async def search_genius(self, query):
        headers = {"Authorization": f"Bearer {self.api_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.genius.com/search?q={urllib.parse.quote(query)}", headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data["response"]["hits"]

    async def get_lyrics_from_url(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
                lyrics_match = re.findall(r'<div[^>]+data-lyrics-container[^>]*>(.*?)</div>', html, re.DOTALL)
                if not lyrics_match:
                    return None
                text = re.sub(r"<.*?>", "", "\n".join(lyrics_match))
                return text.strip()

    @commands.command()
    async def lyrics(self, ctx, *, song: str = None):
        """Shows the lyrics for a song (uses Genius API)."""
        if song is None:
            audio = self.bot.get_cog("Audio")
            if not audio:
                return await ctx.send("❌ Audio cog not found.")

            # Get currently playing track
            player = await audio.get_player(ctx.guild)
            track = player.get_playing_track()

            if not track:
                return await ctx.send("❌ Nothing is currently playing.")
            song = track["title"]

        await ctx.typing()
        results = await self.search_genius(song)
        if not results:
            return await ctx.send("❌ No lyrics found.")

        best = results[0]["result"]
        title = best["full_title"]
        url = best["url"]

        lyrics = await self.get_lyrics_from_url(url)
        if not lyrics:
            return await ctx.send(f"Lyrics page: <{url}>\n❌ Couldn't extract lyrics, please check manually.")

        pages = list(pagify(lyrics, page_length=1900))
        for index, page in enumerate(pages):
            embed = discord.Embed(
                title=title,
                url=url,
                description=page,
                color=discord.Color.purple()
            )
            embed.set_footer(text=f"Page {index+1}/{len(pages)}")
            await ctx.send(embed=embed)
