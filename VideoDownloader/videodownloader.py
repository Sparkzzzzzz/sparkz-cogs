import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
import yt_dlp
import os
import re
import tempfile
import asyncio
import aiohttp
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
            "ffmpeg_location": "",  # Path to ffmpeg if not in system PATH
            "rapidapi_key": "",  # RapidAPI key for Instagram fallback
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
        global_cfg = await self.config.all()
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
        embed.add_field(
            name="Instagram Method",
            value=(
                "ddinstagram proxy → RapidAPI fallback"
                if global_cfg.get("rapidapi_key")
                else "ddinstagram proxy only (no RapidAPI key set)"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

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

    @vdl.command(name="setrapidapi")
    @commands.is_owner()
    async def vdl_setrapidapi(self, ctx: commands.Context, key: str):
        """(Bot owner only) Set a RapidAPI key used as fallback if the proxy fails.

        Get a free key at https://rapidapi.com — search for 'instagram downloader'.
        """
        await self.config.rapidapi_key.set(key)
        await ctx.send(
            "✅ RapidAPI key saved. It will be used as a fallback if the proxy fails."
        )

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

        global_cfg = await self.config.all()
        await self._handle_video(message, url, cfg, global_cfg)

    # ──────────────────────────────────────────────
    # Core download logic
    # ──────────────────────────────────────────────

    async def _handle_video(
        self, message: discord.Message, url: str, cfg: dict, global_cfg: dict
    ):
        max_bytes = cfg["max_filesize_mb"] * 1024 * 1024
        is_instagram = "instagram.com" in url

        async with message.channel.typing():
            video_path = None
            title = "Video"
            last_error = None

            # ── Strategy 1: ddinstagram proxy (Instagram only) ──
            if is_instagram:
                try:
                    proxy_url = self._proxy_instagram_url(url)
                    video_path, title = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self._download_video,
                        proxy_url,
                        max_bytes,
                        global_cfg.get("ffmpeg_location", ""),
                    )
                except FileTooLargeError:
                    raise  # Don't bother falling back if file is just too big
                except Exception as e:
                    last_error = e
                    video_path = None  # Fall through to next strategy

            # ── Strategy 2: yt-dlp direct (Twitter/X, or Instagram proxy failed) ──
            if video_path is None and not is_instagram:
                try:
                    video_path, title = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self._download_video,
                        url,
                        max_bytes,
                        global_cfg.get("ffmpeg_location", ""),
                    )
                except FileTooLargeError:
                    raise
                except Exception as e:
                    last_error = e
                    video_path = None

            # ── Strategy 3: RapidAPI fallback (Instagram only, if proxy failed) ──
            if video_path is None and is_instagram and global_cfg.get("rapidapi_key"):
                try:
                    tmp_dir = tempfile.mkdtemp()
                    video_path, title = await self._download_via_rapidapi(
                        url, tmp_dir, global_cfg["rapidapi_key"], max_bytes
                    )
                except FileTooLargeError:
                    raise
                except Exception as e:
                    last_error = e
                    video_path = None

            # ── All strategies failed ──
            if video_path is None:
                await message.reply(
                    f"❌ Could not download video: `{type(last_error).__name__}: {last_error}`",
                    delete_after=15,
                    mention_author=False,
                )
                return

            # ── Upload to Discord ──
            try:
                file_size = os.path.getsize(video_path)
                if file_size > max_bytes:
                    await message.reply(
                        f"⚠️ Video is too large to upload ({file_size / 1024 / 1024:.1f} MB > {cfg['max_filesize_mb']} MB).",
                        delete_after=15,
                        mention_author=False,
                    )
                    return

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
                try:
                    os.remove(video_path)
                except OSError:
                    pass

    # ──────────────────────────────────────────────
    # Download strategies
    # ──────────────────────────────────────────────

    def _download_video(
        self,
        url: str,
        max_bytes: int,
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
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "*/*",
            },
            "retries": 3,
            "fragment_retries": 3,
        }

        if ffmpeg_location and os.path.isfile(ffmpeg_location):
            ydl_opts["ffmpeg_location"] = str(Path(ffmpeg_location).parent)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Video")
            files = list(Path(tmp_dir).glob("*"))
            if not files:
                raise RuntimeError("yt-dlp ran but no file was saved.")
            return str(files[0]), title

    async def _download_via_rapidapi(
        self,
        url: str,
        tmp_dir: str,
        api_key: str,
        max_bytes: int,
    ) -> tuple[str, str]:
        """Async RapidAPI Instagram downloader fallback. Returns (filepath, title)."""
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "instagram-downloader-download-instagram-videos-stories.p.rapidapi.com",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://instagram-downloader-download-instagram-videos-stories.p.rapidapi.com/index",
                params={"url": url},
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"RapidAPI returned HTTP {resp.status}")
                data = await resp.json()

            # The field name varies slightly between RapidAPI Instagram providers;
            # try the most common ones in order.
            video_url = (
                data.get("media")
                or data.get("url")
                or data.get("video_url")
                or (
                    data.get("links", [{}])[0].get("link")
                    if data.get("links")
                    else None
                )
            )
            if not video_url:
                raise RuntimeError(
                    f"RapidAPI response had no video URL. Response: {data}"
                )

            title = data.get("title") or data.get("caption") or "Instagram Video"

            # Stream the video file
            async with session.get(video_url) as video_resp:
                if video_resp.status != 200:
                    raise RuntimeError(
                        f"Failed to fetch video stream: HTTP {video_resp.status}"
                    )

                content_length = int(video_resp.headers.get("Content-Length", 0))
                if content_length and content_length > max_bytes:
                    raise FileTooLargeError(content_length / (1024 * 1024))

                filename = os.path.join(tmp_dir, "video.mp4")
                with open(filename, "wb") as f:
                    f.write(await video_resp.read())

        return filename, title

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _proxy_instagram_url(url: str) -> str:
        """Rewrite instagram.com to ddinstagram.com — a public proxy that
        serves Instagram reels/posts without requiring login."""
        return re.sub(r"(www\.)?instagram\.com", "ddinstagram.com", url)

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
