import aiohttp
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.commands import Context
from typing import Optional


class SillyCog(commands.Cog):
    """Get your SillyDev server renewal info."""

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
        """Show your SillyDev servers and their renewal days."""
        api_key: Optional[str] = await self.config.api_key()

        if not api_key:
            await ctx.send("❌ No API key found. Use `[p]setsillyapi <key>` first.")
            return

        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        url = "https://panel.sillydev.co.uk/api/client"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return await ctx.send(
                            f"❌ API request failed with status {resp.status}."
                        )

                    servers_data = await resp.json()

                # Build servers field
                servers_list = []
                for server in servers_data.get("data", []):
                    attr = server.get("attributes", {})
                    name = attr.get("name", "Unknown")
                    node = attr.get("node", "Unknown")
                    renewal = attr.get("renewal", "N/A")
                    servers_list.append(
                        f"• **{name}** — renewable in `{renewal}` days (Node: {node})"
                    )

                servers_text = (
                    "\n".join(servers_list) if servers_list else "No servers found."
                )

                embed = discord.Embed(
                    title="🖥️ SillyDev Servers",
                    description=servers_text,
                    color=discord.Color.blue(),
                )

                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ An error occurred:\n```{str(e)}```")