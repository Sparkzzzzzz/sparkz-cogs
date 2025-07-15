import discord
from redbot.core import commands, Config
import aiohttp
from typing import Optional
from redbot.core.utils.chat_formatting import pagify

class Lyrics(commands.Cog):
    """Get song lyrics using Genius."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xABCDEF123456789)
        self.config.register_global(genius_token=None)

    @commands.command(name="setgenius")
    @commands.is_owner()
    async def set_genius_token(self, ctx: commands.Context, token: str):
        """Set Genius API token (owner only, command is deleted)."""
        await self.config.genius_token.set(token)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        await ctx.send("✅ Genius token set successfully.", delete_after=5)

    @commands.command(name="lyricsnow")
    async def lyricsnow(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Get lyrics for a song. Searches current song if no query is given."""
        token = await self.config.genius_token()
        if not token:
            await ctx.send("❌ Genius token is not set. Use `setgenius <token>`.")
            return

        if not query:
            audio = ctx.bot.get_cog("Audio")
            if not audio:
                await ctx.send("❌ Could not get the Audio cog.")
                return

            try:
                state = audio._get_local_audio_state(ctx.guild.id)
                if not state or not state.current:
                    await ctx.send("❌ Nothing is currently playing.")
                    return
                query = state.current.title
            except Exception as e:
                await ctx.send("❌ Could not get the current song from Audio cog.")
                return

        await ctx.channel.typing()

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            params = {"q": query}
            async with session.get("https://api.genius.com/search", headers=headers, params=params) as r:
                if r.status != 200:
                    await ctx.send("❌ Genius API error.")
                    return
                data = await r.json()
                hits = data.get("response", {}).get("hits", [])
                if not hits:
                    await ctx.send("❌ No lyrics found.")
                    return
                url = hits[0]["result"]["url"]

            async with session.get(url) as r:
                text = await r.text()

        # Attempt to extract lyrics from page text
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            await ctx.send("❌ BeautifulSoup4 is not installed. Run `pip install beautifulsoup4`.")
            return

        soup = BeautifulSoup(text, "html.parser")
        lyrics_div = soup.find("div", class_="lyrics") or soup.find("div", class_="Lyrics__Container-sc-...")
        if not lyrics_div:
            await ctx.send("❌ Could not extract lyrics from Genius.")
            return

        lyrics = lyrics_div.get_text(separator="\n").strip()

        pages = list(pagify(lyrics, page_length=1900))
        for page in pages:
            await ctx.send(f"```{page}```")

def setup(bot):
    bot.add_cog(Lyrics(bot))
