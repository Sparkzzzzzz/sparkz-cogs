# mcstats.py
# Redbot Cog: MCStats
# Uses mcstatus.io API to fetch Minecraft server info (Java & Bedrock)
# Place this file in a folder named `mcstats` with an __init__.py and info.json as needed.

import aiohttp
import discord
from redbot.core import commands, checks
from redbot.core.bot import Red

API_BASE = "https://api.mcstatus.io/v2/status"


class MCStats(commands.Cog):
    """Get detailed info about any Minecraft server by IP using mcstatus.io"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def fetch(self, url: str):
        async with self.session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"API error {resp.status}: {text}")
            return await resp.json()

    @commands.command(name="mcstats")
    @commands.cooldown(3, 10, commands.BucketType.user)
    async def mcstats(self, ctx: commands.Context, ip: str, edition: str = "java"):
        """
        Get full status info for a Minecraft server by IP/host.
        Usage: .mcstats <ip> [java|bedrock]
        Example: .mcstats play.hypixel.net java
        """
        edition = edition.lower()
        if edition not in ("java", "bedrock"):
            return await ctx.send("Edition must be `java` or `bedrock`.")

        url = f"{API_BASE}/{edition}/{ip}"
        try:
            data = await self.fetch(url)
        except Exception as e:
            return await ctx.send(f"❌ Failed to fetch server info: {e}")

        if not data.get("online"):
            return await ctx.send(f"🔴 **{ip}** is offline.")

        players = data.get("players", {}) or {}
        online = players.get("online", 0)
        maxp = players.get("max", 0)
        sample = players.get("sample", []) or []

        motd = data.get("motd", {}).get("clean", "").strip()
        version = data.get("version", {}).get("name_clean", "Unknown")
        protocol = data.get("version", {}).get("protocol", "?")
        software = data.get("software", "Unknown")
        hostname = data.get("hostname", ip)
        ipaddr = data.get("ip_address", "?")
        port = data.get("port", "?")
        eula = data.get("eula_blocked")

        embed = discord.Embed(
            title=f"MCStats — {hostname}", color=discord.Color.green()
        )
        embed.add_field(name="Status", value="🟢 Online", inline=True)
        embed.add_field(name="Edition", value=edition.title(), inline=True)
        embed.add_field(name="Players", value=f"{online}/{maxp}", inline=True)
        embed.add_field(
            name="Version", value=f"{version} (protocol {protocol})", inline=True
        )
        embed.add_field(name="Software", value=str(software), inline=True)
        embed.add_field(name="Address", value=f"{ipaddr}:{port}", inline=True)
        if eula is not None:
            embed.add_field(name="EULA Blocked", value=str(eula), inline=True)
        if motd:
            embed.add_field(name="MOTD", value=motd[:1024], inline=False)

        if sample:
            names = ", ".join(p.get("name", "?") for p in sample)
            embed.add_field(
                name="Sample Online Players", value=names[:1024], inline=False
            )
        else:
            embed.add_field(
                name="Sample Online Players",
                value="(Not available — server may have query disabled)",
                inline=False,
            )  # mcstatus.io returns the server icon as a data: URI, which Discord cannot use as a thumbnail URL.
        # So we intentionally skip setting the thumbnail to avoid 400 Bad Request errors.
        # (If you want, I can add code to upload the icon as a file and embed it.)

        # Handle server icon: upload as attachment so Discord can display it
        icon = data.get("icon")
        file = None
        if isinstance(icon, str) and icon.startswith("data:image"):
            try:
                header, b64 = icon.split(",", 1)
                ext = header.split("/")[1].split(";")[0]
                import base64, io

                raw = base64.b64decode(b64)
                buf = io.BytesIO(raw)
                filename = f"server_icon.{ext}"
                file = discord.File(buf, filename=filename)
                embed.set_thumbnail(url=f"attachment://{filename}")
            except Exception:
                pass

        await ctx.send(embed=embed, file=file)


async def setup(bot: Red):
    await bot.add_cog(MCStats(bot))
