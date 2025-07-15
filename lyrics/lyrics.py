import discord
from redbot.core import commands, Config, app_commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.menus import start_adding_reactions, menu
import aiohttp
import asyncio
import textwrap


class Lyrics(commands.Cog):
    """Fetch lyrics for the current playing song."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)
        self.config.register_global(genius_token=None)

    async def get_current_song(self, ctx):
        audio = self.bot.get_cog("Audio")
        if audio is None:
            return None
        try:
            info = await audio.get_playing_track_info(ctx.guild)
            if not info or "title" not in info:
                return None
            title = info.get("title")
            author = info.get("author")
            if title and author:
                return f"{title} {author}"
            return title
        except Exception:
            return None

    async def get_lyrics(self, query: str, token: str):
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            params = {"q": query}
            async with session.get("https://api.genius.com/search", headers=headers, params=params) as resp:
                data = await resp.json()
                hits = data.get("response", {}).get("hits", [])
                if not hits:
                    return None
                lyrics_url = hits[0]["result"]["url"]

            async with session.get(lyrics_url) as r:
                html = await r.text()

        # crude scraping from the genius page
        import re
        m = re.search(r'<div[^>]*?Lyrics__Root[^>]*?>(.*?)</div>', html, re.DOTALL)
        if not m:
            return "Lyrics not found or parsing failed."
        text = re.sub(r"<.*?>", "", m.group(1))  # Remove HTML tags
        return textwrap.dedent(text.strip())

    @commands.command()
    async def lyrics(self, ctx: commands.Context, *, query: str = None):
        """Get lyrics for the current song or a query."""
        async with ctx.typing():
            token = await self.config.genius_token()
            if not token:
                await ctx.send("❌ Genius token not set. Use `set api genius` to set it.")
                return

            song = query or await self.get_current_song(ctx)
            if not song:
                await ctx.send("❌ Could not get the current song from Audio cog.")
                return

            try:
                lyrics_text = await self.get_lyrics(song, token)
                if not lyrics_text:
                    await ctx.send("❌ No lyrics found.")
                    return
            except Exception as e:
                await ctx.send(f"❌ Error retrieving song: {e}")
                return

        pages = [lyrics_text[i:i + 2000] for i in range(0, len(lyrics_text), 2000)]
        embeds = [
            discord.Embed(title=f"Lyrics: {song}", description=box(p), color=discord.Color.blurple())
            for p in pages
        ]
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"Page {i+1}/{len(embeds)}")

        if len(embeds) == 1:
            await ctx.send(embed=embeds[0])
        else:
            await menu(ctx, embeds, {"◀️": 0, "▶️": 1, "❌": 2}, timeout=60)

    @commands.is_owner()
    @commands.command(hidden=True)
    async def set(self, ctx: commands.Context, api: str, *, token: str):
        """Set API tokens. Currently supports: genius"""
        if api.lower() == "genius":
            await self.config.genius_token.set(token)
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await ctx.send("✅ Genius API token set.", delete_after=5)
        else:
            await ctx.send("❌ Unsupported API. Only `genius` is supported.")


async def setup(bot: Red):
    await bot.add_cog(Lyrics(bot))
