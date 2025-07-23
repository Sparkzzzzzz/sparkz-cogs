import aiohttp
from datetime import datetime
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import warning
import discord


class SillyCog(commands.Cog):
    """Check server downtime and credits from SillyDev."""

    def __init__(self, bot: Red):
        self.bot = bot

    @commands.command(name="serverstatus")
    async def server_status(self, ctx):
        """Check how many days till downtime and your credits from SillyDev."""
        # Get API key from Red's api_tokens system
        api_key = await self.bot.get_shared_api_tokens("sillydev")
        token = api_key.get("key")

        if not token:
            return await ctx.send(
                warning("❌ API key not set. Use `.set api sillydev key <your_key>`")
            )

        url = "https://api.sillydev.xyz/server/status"
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return await ctx.send("⚠️ Failed to fetch data from SillyDev API.")
                data = await resp.json()

        expiry_str = data.get("expiry")
        credits = data.get("credits")

        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%dT%H:%M:%SZ")
            days_left = (expiry_date.date() - datetime.utcnow().date()).days
        except Exception:
            return await ctx.send("❌ Invalid expiry date format returned from API.")

        embed = discord.Embed(
            title="📊 SillyDev Server Status", color=discord.Color.orange()
        )
        embed.add_field(
            name="🕒 Days Left", value=f"**{days_left}** days", inline=False
        )
        embed.add_field(name="💰 Credits", value=f"**{credits}** credits", inline=False)
        embed.set_footer(text="Fetched from SillyDev")

        await ctx.send(embed=embed)
