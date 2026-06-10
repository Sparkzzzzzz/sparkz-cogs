import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
import yt_dlp
import os
import re
import tempfile
import asyncio
from pathlib import Path

# Regex to detect Instagram and Twitter/X links
LINK_PATTERN = re.compile(
    r"https?://(www\.)?(instagram\.com/(reel|p|tv)/|twitter\.com/\S+/status/|x\.com/\S+/status/)\S+",
    re.IGNORECASE,
)


class VideoDownloader(commands.Cog):
    """Auto-downloads and reposts videos from Instagram and Twitter/X links."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=9876543210, force_registration=True
        )
        default_guild = {
            "enabled_channels": [],
            "enabled": True,
            "max_filesize_mb": 25,
            "delete_original_message": False,
        }
        default_global = {
            "cookies_file": "",  # Path to cookies.txt for Instagram auth
            "ffmpeg_location": "",  # Path to ffmpeg if not in system PATH
        }
        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

    # ──────────────────────────────────────────────
    # Admin commands
    # ──────────────────────────────────────────────

    @commands.group(name="videodownloader", aliases=["vdl"])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def vdl(self, ctx: commands.Context):
        """Video Downloader settings."""

    @vdl.command(name="toggle")
    async def vdl_toggle(self, ctx: commands.Context):
        """Enable or disable the video downloader for this server."""
        current = await self.config.guild(ctx.guild).enabled()
        await self.config.guild(ctx.guild).enabled.set(not current)
        state = "enabled" if not current else "disabled"
        await ctx.send(f"✅ Video downloader is now **{state}** for this server.")

    @vdl.command(name="addchannel")
    async def vdl_addchannel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Add a channel to watch for links. If none set, all channels are watched."""
        channel = channel or ctx.channel
        async with self.config.guild(ctx.guild).enabled_channels() as channels:
            if channel.id not in channels:
                channels.append(channel.id)
        await ctx.send(f"✅ Now watching {channel.mention} for video links.")

    @vdl.command(name="removechannel")
    async def vdl_removechannel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Remove a channel from the watch list."""
        channel = channel or ctx.channel
        async with self.config.guild(ctx.guild).enabled_channels() as channels:
            if channel.id in channels:
                channels.remove(channel.id)
        await ctx.send(f"✅ No longer watching {channel.mention}.")

    @vdl.command(name="channels")
    async def vdl_channels(self, ctx: commands.Context):
        """List all watched channels."""
        channels = await self.config.guild(ctx.guild).enabled_channels()
        if not channels:
            await ctx.send("📋 Watching **all channels** for video links.")
        else:
            mentions = [f"<#{c}>" for c in channels]
            await ctx.send(f"📋 Watching: {', '.join(mentions)}")

    @vdl.command(name="deleteoriginal")
    async def vdl_deleteoriginal(self, ctx: commands.Context):
        """Toggle whether the original message with the link is deleted after reposting."""
        current = await self.config.guild(ctx.guild).delete_original_message()
        await self.config.guild(ctx.guild).delete_original_message.set(not current)
        state = "will" if not current else "will not"
        await ctx.send(f"✅ Original messages **{state}** be deleted after reposting.")

    @vdl.command(name="maxsize")
    async def vdl_maxsize(self, ctx: commands.Context, mb: int):
        """Set max video file size in MB (default: 25). Use 100 for Nitro servers."""
        if not 1 <= mb <= 500:
            return await ctx.send("❌ Please set a size between 1 and 500 MB.")
        await self.config.guild(ctx.guild).max_filesize_mb.set(mb)
        await ctx.send(f"✅ Max file size set to **{mb} MB**.")

    @vdl.command(name="settings")
    async def vdl_settings(self, ctx: commands.Context):
        """Show current settings."""
        cfg = await self.config.guild(ctx.guild).all()
        channels = cfg["enabled_channels"]
        ch_str = (
            "All channels" if not channels else ", ".join(f"<#{c}>" for c in channels)
        )
        embed = discord.Embed(
            title="Video Downloader Settings", color=discord.Color.blurple()
        )
        embed.add_field(
            name="Enabled", value="✅ Yes" if cfg["enabled"] else "❌ No", inline=True
        )
        embed.add_field(
            name="Max File Size", value=f"{cfg['max_filesize_mb']} MB", inline=True
        )
        embed.add_field(
            name="Delete Original",
            value="✅ Yes" if cfg["delete_original_message"] else "❌ No",
            inline=True,
        )
        embed.add_field(name="Watched Channels", value=ch_str, inline=False)
        await ctx.send(embed=embed)

    @vdl.command(name="setcookies")
    @commands.is_owner()
    async def vdl_setcookies(self, ctx: commands.Context, path: str):
        """(Bot owner only) Set the path to your cookies.txt file for Instagram auth.

        Example: [p]vdl setcookies C:\\cookies\\instagram_cookies.txt
        """
        if not os.path.isfile(path):
            return await ctx.send(f"❌ File not found: `{path}`")
        await self.config.cookies_file.set(path)
        await ctx.send(f"✅ Cookies file set to `{path}`")

    @vdl.command(name="setffmpeg")
    @commands.is_owner()
    async def vdl_setffmpeg(self, ctx: commands.Context, path: str):
        """(Bot owner only) Set the path to ffmpeg if it's not in your system PATH.

        Example: [p]vdl setffmpeg C:\\ffmpeg\\bin\\ffmpeg.exe
        """
        if not os.path.isfile(path):
            return await ctx.send(f"❌ File not found: `{path}`")
        await self.config.ffmpeg_location.set(path)
        await ctx.send(f"✅ ffmpeg location set to `{path}`")

    # ──────────────────────────────────────────────
    # Listener
    # ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        cfg = await self.config.guild(message.guild).all()

        if not cfg["enabled"]:
            return

        # Check channel filter
        watched = cfg["enabled_channels"]
        if watched and message.channel.id not in watched:
            return

        # Find a matching link
        match = LINK_PATTERN.search(message.content)
        if not match:
            return

        url = match.group(0)

        # Download and repost
        global_cfg = await self.config.all()
        await self._handle_video(message, url, cfg, global_cfg)

    # ──────────────────────────────────────────────
    # Core download logic
    # ──────────────────────────────────────────────

    async def _handle_video(
        self, message: discord.Message, url: str, cfg: dict, global_cfg: dict
    ):
        max_bytes = cfg["max_filesize_mb"] * 1024 * 1024

        async with message.channel.typing():
            try:
                video_path, title = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._download_video,
                    url,
                    max_bytes,
                    global_cfg.get("cookies_file", ""),
                    global_cfg.get("ffmpeg_location", ""),
                )
            except FileTooLargeError as e:
                await message.reply(
                    f"⚠️ Video is too large to upload ({e.size_mb:.1f} MB > {cfg['max_filesize_mb']} MB).",
                    delete_after=15,
                    mention_author=False,
                )
                return
            except Exception as e:
                await message.reply(
                    f"❌ Could not download video: `{type(e).__name__}: {e}`",
                    delete_after=15,
                    mention_author=False,
                )
                return

            try:
                file_size = os.path.getsize(video_path)
                if file_size > max_bytes:
                    raise FileTooLargeError(file_size / (1024 * 1024))

                platform = self._detect_platform(url)
                caption = f"📹 **{title}** — via **{platform}**"

                await message.reply(
                    caption,
                    file=discord.File(video_path, filename=Path(video_path).name),
                    mention_author=False,
                )

                if cfg["delete_original_message"]:
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        pass

            finally:
                # Clean up temp file
                try:
                    os.remove(video_path)
                except OSError:
                    pass

    def _download_video(
        self,
        url: str,
        max_bytes: int,
        cookies_file: str = "",
        ffmpeg_location: str = "",
    ) -> tuple[str, str]:
        """Synchronous yt-dlp download. Returns (filepath, title)."""
        tmp_dir = tempfile.mkdtemp()
        output_template = os.path.join(tmp_dir, "%(title).50s.%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "max_filesize": max_bytes,
            # Spoof a real browser to bypass Instagram's login wall for public reels
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "*/*",
                "Referer": "https://www.instagram.com/",
            },
            # Retry on transient failures
            "retries": 3,
            "fragment_retries": 3,
        }

        if cookies_file and os.path.isfile(cookies_file):
            ydl_opts["cookiefile"] = cookies_file

        if ffmpeg_location and os.path.isfile(ffmpeg_location):
            ydl_opts["ffmpeg_location"] = str(Path(ffmpeg_location).parent)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Video")
            # Find the downloaded file
            files = list(Path(tmp_dir).glob("*"))
            if not files:
                raise RuntimeError("yt-dlp ran but no file was saved.")
            return str(files[0]), title

    @staticmethod
    def _detect_platform(url: str) -> str:
        if "instagram.com" in url:
            return "Instagram"
        if "twitter.com" in url or "x.com" in url:
            return "Twitter / X"
        return "Unknown"


class FileTooLargeError(Exception):
    def __init__(self, size_mb: float):
        self.size_mb = size_mb
        super().__init__(f"File too large: {size_mb:.1f} MB")
