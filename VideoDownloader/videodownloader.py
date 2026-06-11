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

# Regex to detect Instagram, Twitter/X, and TikTok links
LINK_PATTERN = re.compile(
    r"https?://(www\.|vm\.|vt\.|m\.)?(instagram\.com/(reel|p|tv)/|twitter\.com/\S+/status/|x\.com/\S+/status/|tiktok\.com/\S+|tiktok\.com/t/\S+)\S*",
    re.IGNORECASE,
)

TIKWM_API = "https://www.tikwm.com/api/"


class VideoDownloader(commands.Cog):
    """Auto-downloads and reposts videos from Instagram, Twitter/X, and TikTok links."""

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
            "ffmpeg_location": "",
            "rapidapi_key": "",
            "cookies_file": "",
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
                "yt-dlp direct (with cookies) → RapidAPI fallback"
                if global_cfg.get("rapidapi_key") and global_cfg.get("cookies_file")
                else (
                    "yt-dlp direct (with cookies)"
                    if global_cfg.get("cookies_file")
                    else (
                        "yt-dlp direct → RapidAPI fallback"
                        if global_cfg.get("rapidapi_key")
                        else "yt-dlp direct only (no cookies or RapidAPI key set)"
                    )
                )
            ),
            inline=False,
        )
        embed.add_field(
            name="TikTok Method",
            value="tikwm.com API (no key required)",
            inline=False,
        )
        embed.add_field(
            name="Cookies File",
            value=(
                f"`{global_cfg['cookies_file']}`"
                if global_cfg.get("cookies_file")
                else "Not set"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @vdl.command(name="setffmpeg")
    @commands.is_owner()
    async def vdl_setffmpeg(self, ctx: commands.Context, path: str):
        """(Bot owner only) Set the path to ffmpeg if it's not in your system PATH."""
        if not os.path.isfile(path):
            return await ctx.send(f"❌ File not found: `{path}`")
        await self.config.ffmpeg_location.set(path)
        await ctx.send(f"✅ ffmpeg location set to `{path}`")

    @vdl.command(name="setrapidapi")
    @commands.is_owner()
    async def vdl_setrapidapi(self, ctx: commands.Context, key: str):
        """(Bot owner only) Set a RapidAPI key used as fallback if yt-dlp fails for Instagram."""
        await self.config.rapidapi_key.set(key)
        await ctx.send(
            "✅ RapidAPI key saved. It will be used as a fallback if yt-dlp fails."
        )

    @vdl.command(name="setcookies")
    @commands.is_owner()
    async def vdl_setcookies(self, ctx: commands.Context, path: str):
        """(Bot owner only) Set the path to a Netscape-format cookies.txt file for Instagram."""
        if not os.path.isfile(path):
            return await ctx.send(f"❌ File not found: `{path}`")
        await self.config.cookies_file.set(path)
        await ctx.send(f"✅ Cookies file set to `{path}`")

    @vdl.command(name="clearcookies")
    @commands.is_owner()
    async def vdl_clearcookies(self, ctx: commands.Context):
        """(Bot owner only) Clear the configured cookies file."""
        await self.config.cookies_file.set("")
        await ctx.send("✅ Cookies file cleared.")

    # ──────────────────────────────────────────────
    # Listener
    # ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = await self.config.guild(message.guild).all()

        if not cfg["enabled"]:
            return

        watched = cfg["enabled_channels"]
        if watched and message.channel.id not in watched:
            return

        match = LINK_PATTERN.search(message.content)
        if not match:
            return

        url = match.group(0)
        global_cfg = await self.config.all()

        asyncio.create_task(self._handle_video(message, url, cfg, global_cfg))

    # ──────────────────────────────────────────────
    # Core download logic
    # ──────────────────────────────────────────────

    async def _handle_video(
        self, message: discord.Message, url: str, cfg: dict, global_cfg: dict
    ):
        max_bytes = cfg["max_filesize_mb"] * 1024 * 1024
        is_instagram = "instagram.com" in url
        is_tiktok = "tiktok.com" in url

        video_path = None
        title = "Video"
        last_error = None

        try:
            if is_tiktok:
                # ── TikTok: always use tikwm.com API ──
                try:
                    tmp_dir = tempfile.mkdtemp()
                    video_path, title = await self._download_via_tikwm(
                        url, tmp_dir, max_bytes
                    )
                except FileTooLargeError:
                    raise
                except Exception as e:
                    last_error = e
                    video_path = None
            else:
                # ── Strategy 1: yt-dlp direct (Instagram / Twitter / X) ──
                try:
                    video_path, title = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self._download_video,
                        url,
                        max_bytes,
                        global_cfg.get("ffmpeg_location", ""),
                        global_cfg.get("cookies_file", ""),
                    )
                except FileTooLargeError:
                    raise
                except Exception as e:
                    last_error = e
                    video_path = None

                # ── Strategy 2: RapidAPI fallback (Instagram only) ──
                if (
                    video_path is None
                    and is_instagram
                    and global_cfg.get("rapidapi_key")
                ):
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

        except FileTooLargeError as e:
            await message.reply(
                f"⚠️ Video is too large to upload ({e.size_mb:.1f} MB > {cfg['max_filesize_mb']} MB).",
                delete_after=15,
                mention_author=False,
            )
            return

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
        cookies_file: str = "",
    ) -> tuple[str, str]:
        """Synchronous yt-dlp download. Returns (filepath, title)."""
        tmp_dir = tempfile.mkdtemp()
        output_template = os.path.join(tmp_dir, "%(title).50s.%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "format": "best[ext=mp4]/best/bestvideo*+bestaudio",
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

        if cookies_file and os.path.isfile(cookies_file):
            ydl_opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Video")
            files = list(Path(tmp_dir).glob("*"))
            if not files:
                raise RuntimeError("yt-dlp ran but no file was saved.")
            return str(files[0]), title

    async def _download_via_tikwm(
        self,
        url: str,
        tmp_dir: str,
        max_bytes: int,
    ) -> tuple[str, str]:
        """Download TikTok video via tikwm.com API (no watermark). Returns (filepath, title)."""
        async with aiohttp.ClientSession() as session:
            # tikwm accepts short URLs directly — no need to expand first
            async with session.get(
                TIKWM_API,
                params={"url": url, "hd": 1},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"tikwm API returned HTTP {resp.status}")
                data = await resp.json(content_type=None)

            if data.get("code") != 0:
                raise RuntimeError(
                    f"tikwm API error {data.get('code')}: {data.get('msg', 'unknown error')}"
                )

            video_data = data.get("data", {})
            # Prefer HD play URL, fall back to standard play URL
            video_url = video_data.get("hdplay") or video_data.get("play")
            if not video_url:
                raise RuntimeError(f"tikwm returned no video URL. Response: {data}")

            title = (video_data.get("title") or "TikTok Video")[:100]

            async with session.get(
                video_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as video_resp:
                if video_resp.status != 200:
                    raise RuntimeError(
                        f"Failed to fetch TikTok video stream: HTTP {video_resp.status}"
                    )

                content_length = int(video_resp.headers.get("Content-Length", 0))
                if content_length and content_length > max_bytes:
                    raise FileTooLargeError(content_length / (1024 * 1024))

                filename = os.path.join(tmp_dir, "tiktok_video.mp4")
                with open(filename, "wb") as f:
                    f.write(await video_resp.read())

        actual_size = os.path.getsize(filename)
        if actual_size > max_bytes:
            raise FileTooLargeError(actual_size / (1024 * 1024))

        return filename, title

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
    def _detect_platform(url: str) -> str:
        if "instagram.com" in url:
            return "Instagram"
        if "twitter.com" in url or "x.com" in url:
            return "Twitter / X"
        if "tiktok.com" in url:
            return "TikTok"
        return "Unknown"


class FileTooLargeError(Exception):
    def __init__(self, size_mb: float):
        self.size_mb = size_mb
        super().__init__(f"File too large: {size_mb:.1f} MB")
