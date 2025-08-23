import aiohttp
import discord
from discord import ui
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.commands import Context
from typing import Optional, List

STATUS_EMOJIS = {
    "running": "🟢",
    "online": "🟢",
    "offline": "🔴",
    "stopped": "🔴",
    "restarting": "🟡",
    "unknown": "⚪",
    None: "⚪",
}


class SillyCog(commands.Cog):
    """Get your SillyDev server info with renewal, maintenance, and status."""

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
        """Show your SillyDev servers with renewal, maintenance, and status in a paginated embed."""
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
                    data = await resp.json()

            servers = data.get("data", [])
            if not servers:
                return await ctx.send("❌ No servers found.")

            # Prepare pages
            pages: List[discord.Embed] = []
            for server in servers:
                attr = server.get("attributes", {})
                name = attr.get("name") or "Unknown"
                node = attr.get("node") or "Unknown"
                renewal = str(attr.get("renewal") or "N/A")
                maintenance = (
                    "Scheduled" if attr.get("is_node_under_maintenance") else "None"
                )
                status_raw = attr.get("status") or "unknown"
                status_icon = STATUS_EMOJIS.get(status_raw.lower(), "⚪")
                status_text = status_raw.capitalize() if status_raw else "Unknown"

                embed = discord.Embed(title=name, color=discord.Color.blue())
                embed.description = (
                    f"- 🌐 Node: `{node}`\n"
                    f"- {status_icon} Status: {status_text}\n"
                    f"- 📅 Renewal: {renewal} days\n"
                    f"- 🔧 Node Maintenance: {maintenance}"
                )
                pages.append(embed)

            # Send first page with buttons
            view = ServerPages(pages)
            await ctx.send(embed=pages[0], view=view)

        except Exception as e:
            await ctx.send(f"❌ An error occurred:\n```{str(e)}```")


class ServerPages(ui.View):
    """Discord UI View for paginated server embeds."""

    def __init__(self, pages: List[discord.Embed]):
        super().__init__(timeout=180)
        self.pages = pages
        self.current = 0

    async def update_message(self, interaction: discord.Interaction):
        """Update the message embed for the current page."""
        await interaction.response.edit_message(
            embed=self.pages[self.current], view=self
        )

    @ui.button(emoji="⬅️", style=discord.ButtonStyle.gray)
    async def previous(self, button: ui.Button, interaction: discord.Interaction):
        self.current = (self.current - 1) % len(self.pages)
        await self.update_message(interaction)

    @ui.button(emoji="❌", style=discord.ButtonStyle.gray)
    async def close(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.message.delete()
        self.stop()

    @ui.button(emoji="➡️", style=discord.ButtonStyle.gray)
    async def next(self, button: ui.Button, interaction: discord.Interaction):
        self.current = (self.current + 1) % len(self.pages)
        await self.update_message(interaction)
