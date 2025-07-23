from redbot.core import commands, Config
import aiohttp


class SillyCog(commands.Cog):
    """Check SillyDev panel for server status like days until downtime."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_global(api_key=None)

    @commands.command(name="setapi")
    @commands.is_owner()
    async def set_api_key(self, ctx, key: str):
        """Set your SillyDev panel API key."""
        await self.config.api_key.set(key)
        await ctx.send("✅ API key has been set successfully.")

    @commands.command(name="serverstatus")
    async def check_server_status(self, ctx):
        """Check days until server downtime from SillyDev panel."""
        api_key = await self.config.api_key()
        if not api_key:
            return await ctx.send("❌ API key not set. Use `.setapi <key>` first.")

        url = "https://panel.sillydev.co.uk/api/client"
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return await ctx.send(f"❌ API Error: {resp.status}")
                data = await resp.json()

        try:
            first_server = data["data"][0]["attributes"]
            server_name = first_server["name"]
            renewal_days = first_server["renewal"]
            await ctx.send(
                f"🖥️ **{server_name}**\n"
                f"⏳ Days left until downtime: **{renewal_days}**"
            )
        except Exception as e:
            await ctx.send(f"⚠️ Failed to parse response: `{e}`")