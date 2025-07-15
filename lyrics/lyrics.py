import discord
from redbot.core import commands, Config
import aiohttp
from typing import Optional
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

GENIUS_API_BASE = "https://api.genius.com"

class Lyrics(commands.Cog):
    """Get song lyrics using Genius"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_global(token=None)

    @commands.is_owner()
    @commands.command()
    async def setgeniustoken(self, ctx, token: str):
        """Set Genius API token. (Hidden from logs)"""
        await ctx.message.delete()
        await self.config.token.set(token)
        try:
            await ctx.message.add_reaction("✅")
        except discord.HTTPException:
            await ctx.send("✅ Token set.", delete_after=5)

    @commands.command()
    async def lyrics(self, ctx, *, song: Optional[str] = None):
        """Get lyrics for the currently playing song or a given name."""
        token = await self.config.token()
        if not token:
            return await ctx.send("❌ Genius token not set. Use `[p]setgeniustoken`.")

        if not song:
            # Get currently playing song using Audio API
            audio = self.bot.get_cog("Audio")
            if not audio:
                return await ctx.send("❌ Audio cog not loaded.")
            try:
                info = await audio.get_playing_track_info(ctx.guild)
                if not info or "title" not in info or "author" not in info:
                    raise ValueError
                song = f"{info['author']} {info['title']}"
            except Exception:
                return await ctx.send("❌ Could not get the current song from Audio cog.")

        await ctx.trigger_typing()
        try:
            lyrics_text = await self.get_lyrics(song, token)
        except Exception as e:
            return await ctx.send(f"❌ Error retrieving lyrics: {e}")

        if not lyrics_text:
            return await ctx.send("❌ No lyrics found.")

        pages = [lyrics_text[i:i+2000] for i in range(0, len(lyrics_text), 2000)]
        embeds = [discord.Embed(description=page, color=discord.Color.blurple()).set_footer(text=f"Page {i+1}/{len(pages)}") for i, page in enumerate(pages)]
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    async def get_lyrics(self, query, token):
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GENIUS_API_BASE}/search", params={"q": query}, headers=headers) as resp:
                data = await resp.json()
                hits = data["response"]["hits"]
                if not hits:
                    return None
                song_path = hits[0]["result"]["path"]

            # Now fetch lyrics page from Genius (HTML scrape)
            async with session.get(f"https://genius.com{song_path}") as response:
                html = await response.text()

        # Strip lyrics using crude parsing
        import re
        lyrics = re.findall(r'<div[^>]+data-lyrics-container="true"[^>]*>(.*?)</div>', html, re.DOTALL)
        lyrics_text = "\n".join([re.sub(r'<[^>]+>', '', block).strip() for block in lyrics])
        return lyrics_text.strip() if lyrics_text else None
