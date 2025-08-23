import aiohttp
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.commands import Context
from typing import Optional


class SillyCog(commands.Cog):
    """Get your SillyDev uptime info."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_global(api_key=None)

    @commands.is_owner()
    @commands.command(name="setsillyapi")
    async def set_api_key(self, ctx: Context, key: str):
        """Set your SillyDev API key."""
        await self.config.api_key.set(key)
        await ctx.send("✅ SillyDev API key saved!")

    @commands.is_owner()
    @commands.command(name="sillystats")
    async def silly_stats(self, ctx: Context):
        """Show your SillyDev uptime days left."""
        api_key: Optional[str] = await self.config.api_key()

        if not api_key:
            await ctx.send("❌ No API key found. Use `[p]setsillyapi <key>` first.")
            return

        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

        url = "https://panel.sillydev.co.uk/api/client/store"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return await ctx.send(
                            f"❌ API request failed with status {resp.status}."
                        )

                    data = await resp.json()

                    # Extract uptime days left
                    uptime_days = (
                        data.get("attributes", {})
                        .get("uptime", {})
                        .get("days_left", None)
                    )

                    if uptime_days is None:
                        return await ctx.send(
                            "❌ Could not find `uptime.days_left` in API response."
                        )

                    embed = discord.Embed(
                        title="⏳ SillyDev Uptime",
                        description=f"**Days Left:** `{uptime_days}`",
                        color=discord.Color.blue(),
                    )
                    await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ An error occurred:\n```{str(e)}```")
