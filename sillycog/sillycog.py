import aiohttp
import discord
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
        """Show your SillyDev servers with renewal, maintenance, and status using reactions for pagination."""
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

            # Prepare embeds for each server
            pages: List[discord.Embed] = []
            for idx, server in enumerate(servers, start=1):
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
                    f"- 🔧 Node Maintenance: {maintenance}\n\n"
                    f"Page {idx}/{len(servers)}"
                )
                pages.append(embed)

            current = 0
            message = await ctx.send(embed=pages[current])

            if len(pages) == 1:
                return  # Only one server, no reactions needed

            # Add navigation reactions
            await message.add_reaction("⬅️")
            await message.add_reaction("❌")
            await message.add_reaction("➡️")

            def check(reaction, user):
                return (
                    user == ctx.author
                    and str(reaction.emoji) in ["⬅️", "➡️", "❌"]
                    and reaction.message.id == message.id
                )

            while True:
                try:
                    reaction, user = await ctx.bot.wait_for(
                        "reaction_add", timeout=15.0, check=check
                    )
                except TimeoutError:
                    # Remove all reactions after 15 secs of inactivity
                    try:
                        await message.clear_reactions()
                    except discord.Forbidden:
                        pass
                    break

                if str(reaction.emoji) == "❌":
                    await message.delete()
                    break
                elif str(reaction.emoji) == "⬅️":
                    current = (current - 1) % len(pages)
                    await message.edit(embed=pages[current])
                elif str(reaction.emoji) == "➡️":
                    current = (current + 1) % len(pages)
                    await message.edit(embed=pages[current])

                # Remove user's reaction for cleaner interface
                try:
                    await message.remove_reaction(reaction, user)
                except discord.Forbidden:
                    pass  # Bot may not have permission

        except Exception as e:
            await ctx.send(f"❌ An error occurred:\n```{str(e)}```")
