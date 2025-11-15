import discord
from discord.ext import commands
from redbot.core import commands as red_commands, Config
from redbot.core.bot import Red
import aiohttp
import asyncio
import time
import json

# ---------------- Vigenere ----------------
alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789{}[]:\"',.<>?/\\|!@#$%^&*()-_=+ \n\t"


def vigenere_decrypt(ciphertext: str, key: str) -> str:
    key = (key * (len(ciphertext) // len(key) + 1))[: len(ciphertext)]
    res = []
    for c, k in zip(ciphertext, key):
        if c in alphabet:
            shift = alphabet.index(k) % len(alphabet)
            res.append(alphabet[(alphabet.index(c) - shift) % len(alphabet)])
        else:
            res.append(c)
    return "".join(res)


class VerifierPlus(red_commands.Cog):
    """Verification system that works with external API codes"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=9876543210, force_registration=True
        )
        default_global = {"api_url": None, "enc_key": "LENSHRIDHUZZ", "role_id": None}
        self.config.register_global(**default_global)

    # ---------------- Setup Commands ----------------
    @red_commands.group()
    async def verifyset(self, ctx):
        """Configure VerifierPlus"""
        pass

    @verifyset.command()
    async def api(self, ctx, url: str):
        """Set the API base URL (e.g., http://194.164.125.5:6439)"""
        await self.config.api_url.set(url.rstrip("/"))
        await ctx.send(f"✅ API URL set to: {url}")

    @verifyset.command()
    async def role(self, ctx, role: discord.Role):
        """Set the role to assign on successful verification"""
        await self.config.role_id.set(role.id)
        await ctx.send(f"✅ Role set to: {role.name}")

    @verifyset.command()
    async def key(self, ctx, key: str):
        """Set the Vigenere encryption key"""
        await self.config.enc_key.set(key)
        await ctx.send("✅ Encryption key updated.")

    # ---------------- Event Listener ----------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        api_url = await self.config.api_url()
        enc_key = await self.config.enc_key()
        role_id = await self.config.role_id()

        if not api_url or not role_id:
            return  # Not configured

        try:
            now = int(time.time())
            expiry = now + 120  # 2 minutes from now
            embed = discord.Embed(
                title="Verification Required",
                description=(
                    f"Welcome {member.mention}!\n\n"
                    "Please reply **in this DM** with your code.\n\n"
                    f"You have until <t:{expiry}:R> to respond."
                ),
                color=discord.Color.blurple(),
            )
            await member.send(embed=embed)
        except discord.Forbidden:
            await member.kick(reason="Verification failed (DMs closed)")
            return

        def check(m: discord.Message):
            return m.author == member and isinstance(m.channel, discord.DMChannel)

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120.0)
            user_code = msg.content.strip()

            # Call API /verify/{code}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{api_url}/verify/{user_code}") as r:
                    encrypted = await r.text()
                    decrypted = vigenere_decrypt(encrypted, enc_key)
                    result = json.loads(decrypted)

            if result.get("valid"):
                role = member.guild.get_role(role_id)
                if role:
                    await member.add_roles(role, reason="User verified")
                await member.send("✅ You have been verified and given access!")
            else:
                await member.send("❌ Invalid or expired code. You will be removed.")
                await member.kick(reason="Invalid verification code")

        except asyncio.TimeoutError:
            await member.send("⏳ Time expired. You will be removed.")
            await member.kick(reason="Verification timeout")
