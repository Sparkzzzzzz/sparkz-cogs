import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import pagify
import aiohttp
import urllib.parse

class Lyrics(commands.Cog):
    """Get lyrics for the current or a specific song using Genius."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.api_url = "https://api.genius.com/search"
        self.base_url = "https://genius.com"
        self.token = "Bearer JQsq0lmytqE7mga6Sh4HmZcPp-C9aEVkQzOUze2pwMHn3NcFbZ2gB1mmjKR_WQ0U"  # Replace this with your Genius token

    @commands.command()
    async def lyrics(self, ctx: commands.Context, *, song: str = None):
        """Get lyrics for the currently playing or a specified song."""
        await ctx.typing()

        # Get currently playing song title if not specified
        if song is None:
            audio_cog = ctx.bot.get_cog("Audio")
            if not audio_cog:
                return await ctx.send("❌ Audio cog not loaded.")
            try:
                player = audio_cog._guild_states.get(ctx.guild.id)
                if not player or not player.queue or not player.queue.current:
                    return await ctx.send("❌ No song currently playing.")
                song = player.queue.current.title
            except Exception as e:
                return await ctx.send(f"❌ Error retrieving song: {e}")

        headers = {
            "Authorization": self.token
        }

        async with aiohttp.ClientSession() as session:
            params = {"q": song}
            async with session.get(self.api_url, headers=headers, params=params) as resp:
                data = await resp.json()

            hits = data.get("response", {}).get("hits")
            if not hits:
                return await ctx.send("❌ No lyrics found.")

            url = hits[0]["result"]["url"]

            # Scrape lyrics from the song URL
            async with session.get(url) as page_resp:
                html = await page_resp.text()

        # Naive scraping (can be improved using regex or BeautifulSoup via bs4)
        try:
            import re
            from html import unescape
            raw = re.findall(r'<div class="Lyrics__Container.*?">(.*?)</div>', html, re.DOTALL)
            text = "\n".join(re.sub(r"<.*?>", "", unescape(x)) for x in raw)
            if not text.strip():
                raise ValueError
        except Exception:
            return await ctx.send(f"🔗 [Lyrics Link]({url})\n⚠️ Couldn’t extract full lyrics. View on Genius.")

        pages = list(pagify(text, delims=["\n\n", "\n", " "], page_length=2000))

        for i, page in enumerate(pages):
            embed = discord.Embed(
                title=f"Lyrics: {song}",
                description=page,
                color=discord.Color.green()
            )
            if len(pages) > 1:
                embed.set_footer(text=f"Page {i+1}/{len(pages)}")
            await ctx.send(embed=embed)