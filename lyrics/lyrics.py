import discord
from redbot.core import commands, Config, app_commands
import aiohttp
import asyncio

GENIUS_API_URL = "https://api.genius.com"

class Lyrics(commands.Cog):
    """Get song lyrics using Genius"""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.config = Config.get_conf(self, identifier=6723540)
        self.config.register_global(token=None)

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    @commands.is_owner()
    @commands.command(name="setgeniustoken")
    async def set_genius_token(self, ctx, token: str):
        """Set the Genius API token"""
        await self.config.token.set(token)
        await ctx.send("✅ Genius API token set!")

    @commands.command(aliases=["lyric"])
    async def lyrics(self, ctx, *, song: str = None):
        """Get lyrics for the current or given song"""
        token = await self.config.token()
        if not token:
            return await ctx.send("❌ Genius token not set. Use `[p]setgeniustoken <token>`")

        if song is None:
            audio_cog = ctx.bot.get_cog("Audio")
            if not audio_cog:
                return await ctx.send("❌ Audio cog not loaded.")
            try:
                player = await audio_cog.get_player(ctx.guild)
                if not player or not player.current:
                    return await ctx.send("❌ No song currently playing.")
                song = player.current.title
            except Exception:
                return await ctx.send("❌ Could not get the current song from Audio cog.")

        async with self.session.get(
            f"{GENIUS_API_URL}/search",
            params={"q": song},
            headers={"Authorization": f"Bearer {token}"}
        ) as resp:
            data = await resp.json()

        hits = data.get("response", {}).get("hits", [])
        if not hits:
            return await ctx.send("❌ No lyrics found.")

        song_data = hits[0]["result"]
        url = song_data["url"]
        title = song_data["full_title"]

        # Scrape the lyrics from the Genius webpage
        async with self.session.get(url) as r:
            text = await r.text()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        lyrics_div = soup.find("div", class_="Lyrics__Container-sc-1ynbvzw-6")
        if not lyrics_div:
            return await ctx.send("❌ Couldn't extract lyrics from Genius page.")

        lyrics = lyrics_div.get_text(separator="\n").strip()
        pages = [lyrics[i:i+2000] for i in range(0, len(lyrics), 2000)]

        embeds = []
        for i, page in enumerate(pages):
            embed = discord.Embed(
                title=title if i == 0 else f"{title} (Page {i+1})",
                description=page,
                url=url,
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            embeds.append(embed)

        await self.paginate(ctx, embeds)

    async def paginate(self, ctx, embeds):
        """Paginate embeds with reactions"""
        if len(embeds) == 1:
            return await ctx.send(embed=embeds[0])

        current = 0
        message = await ctx.send(embed=embeds[current])
        await message.add_reaction("◀️")
        await message.add_reaction("▶️")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"] and reaction.message.id == message.id

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                await message.remove_reaction(reaction, user)

                if str(reaction.emoji) == "▶️" and current < len(embeds) - 1:
                    current += 1
                    await message.edit(embed=embeds[current])
                elif str(reaction.emoji) == "◀️" and current > 0:
                    current -= 1
                    await message.edit(embed=embeds[current])
            except asyncio.TimeoutError:
                break