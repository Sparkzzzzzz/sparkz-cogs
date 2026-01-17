# mcstats.py
# Redbot Cog: MCStats (Advanced)
# Uses mcstatus.io API + direct Minecraft Query protocol to fetch player list even when API can't

import aiohttp
import discord
import asyncio
import struct
import socket
import base64
import io
from redbot.core import commands
from redbot.core.bot import Red

API_BASE = "https://api.mcstatus.io/v2/status"


class MCStats(commands.Cog):
    """Get detailed info about any Minecraft server by IP using mcstatus.io + deep scan"""

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

    def query_players(self, host: str, port: int = 25565):
        """Direct Minecraft Query protocol to fetch full player list (blocking)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)

            # Handshake
            sock.sendto(b"\xfe\xfd\x09\x00\x00\x00\x01", (host, port))
            data, _ = sock.recvfrom(2048)
            token = int(data[5:].strip())

            # Full stat request
            req = (
                b"\xfe\xfd\x00\x00\x00\x00\x01"
                + struct.pack(">i", token)
                + b"\x00\x00\x00\x00"
            )
            sock.sendto(req, (host, port))
            data, _ = sock.recvfrom(65535)
            sock.close()

            parts = data.split(b"\x00\x00\x01player_\x00\x00")
            if len(parts) < 2:
                return []
            players = parts[1].split(b"\x00")
            return [p.decode("utf-8", errors="ignore") for p in players if p]
        except Exception:
            return []

    @commands.command(name="mcstats")
    @commands.cooldown(3, 10, commands.BucketType.user)
    async def mcstats(self, ctx: commands.Context, ip: str, edition: str = "java"):
        """
        Get full status info for a Minecraft server by IP/host.
        Usage: .mcstats <ip> [java|bedrock]
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
        motd = data.get("motd", {}).get("clean", "").strip()
        version = data.get("version", {}).get("name_clean", "Unknown")
        protocol = data.get("version", {}).get("protocol", "?")
        software = data.get("software", "Unknown")
        hostname = data.get("hostname", ip)
        ipaddr = data.get("ip_address", ip)
        port = int(data.get("port", 25565))

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
        if motd:
            embed.add_field(name="MOTD", value=motd[:1024], inline=False)

        # Deep scan player list (Java only)
        deep_players = []
        if edition == "java":
            loop = asyncio.get_running_loop()
            deep_players = await loop.run_in_executor(
                None, self.query_players, ipaddr, port
            )

        if deep_players:
            names = ", ".join(deep_players)
            embed.add_field(
                name="Online Players (Deep Scan)", value=names[:1024], inline=False
            )
        else:
            embed.add_field(
                name="Online Players",
                value="(Not available — server blocks query)",
                inline=False,
            )

        # Server icon upload
        icon = data.get("icon")
        file = None
        if isinstance(icon, str) and icon.startswith("data:image"):
            try:
                header, b64 = icon.split(",", 1)
                ext = header.split("/")[1].split(";")[0]
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
