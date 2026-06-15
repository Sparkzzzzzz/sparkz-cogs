import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import Optional
import math
import re
import asyncio
import logging

log = logging.getLogger("red.counting")

# Safe math evaluation — allows numbers, basic operators, AND named math functions
SAFE_MATH_PATTERN = re.compile(
    r"^[\d\s\+\-\*\/\(\)\.\%]+"
    r"|^(sqrt|floor|ceil|pow|abs|round)\s*\([\d\s\+\-\*\/\(\)\.\%\,]+\)$"
)

# Full pattern that permits math function calls mixed with expressions
SAFE_MATH_FULL = re.compile(
    r"^[\d\s\+\-\*\/\(\)\.\%]*((?:sqrt|floor|ceil|pow|abs|round)\s*\([\d\s\+\-\*\/\(\)\.\%\,]*\)[\s\+\-\*\/\(\)\.\%\d]*)*$"
)


def safe_eval(expr: str) -> Optional[float]:
    """Evaluate a math expression safely. Returns None if invalid."""
    expr = expr.strip()

    # Allow expressions containing only digits, operators, parens, decimals, and math functions
    allowed = re.compile(r"^[\d\s\+\-\*\/\(\)\.\%]|sqrt|floor|ceil|pow|abs|round")
    # Whitelist: only these characters and function names are permitted
    sanitized = re.sub(r"(sqrt|floor|ceil|pow|abs|round)", "", expr)
    if not re.match(r"^[\d\s\+\-\*\/\(\)\.\%,]*$", sanitized):
        return None

    try:
        result = eval(
            expr,
            {"__builtins__": {}},
            {
                "abs": abs,
                "round": round,
                "pow": pow,
                "sqrt": math.sqrt,
                "floor": math.floor,
                "ceil": math.ceil,
            },
        )
        if (
            isinstance(result, (int, float))
            and not math.isinf(result)
            and not math.isnan(result)
        ):
            return float(result)
    except Exception:
        pass
    return None


class Counting(commands.Cog):
    """A counting game cog. Count up together — don't break the chain!"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=0xC0C0C0, force_registration=True
        )

        default_guild = {
            "channel_id": None,
            "enabled": False,
            "current_count": 0,
            "last_user_id": None,
            "start_number": 0,
            "tick_reaction": "✅",
            "wrong_reaction": "❌",
            # Persistent reset confirmation state
            "pending_reset": False,  # True while awaiting confirmation
            "pending_reset_msg_id": None,  # Message ID of the confirmation prompt
        }
        self.config.register_guild(**default_guild)

        # In-memory tasks — rebuilt on ready from persisted state
        self._pending_resets: dict[int, asyncio.Task] = {}

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_ready(self):
        """Restore any pending reset confirmations that survived a restart."""
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            if not data.get("pending_reset"):
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                # Bot can't see the guild; clear stale state
                await self.config.guild_from_id(guild_id).pending_reset.set(False)
                await self.config.guild_from_id(guild_id).pending_reset_msg_id.set(None)
                continue

            msg_id = data.get("pending_reset_msg_id")
            channel_id = data.get("channel_id")
            if not msg_id or not channel_id:
                await self.config.guild(guild).pending_reset.set(False)
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                await self.config.guild(guild).pending_reset.set(False)
                continue

            try:
                confirm_msg = await channel.fetch_message(msg_id)
            except (discord.NotFound, discord.HTTPException):
                # Message is gone — treat as timed out
                await self.config.guild(guild).pending_reset.set(False)
                await self.config.guild(guild).pending_reset_msg_id.set(None)
                continue

            # Re-attach a wait_for task to the existing message
            task = asyncio.create_task(
                self._wait_for_reset_confirm(guild, confirm_msg, restored=True)
            )
            self._pending_resets[guild_id] = task

    def cog_unload(self):
        for task in self._pending_resets.values():
            task.cancel()

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    async def _reset_count(self, guild: discord.Guild):
        """Reset the count back to the configured start number."""
        cfg = self.config.guild(guild)
        start = await cfg.start_number()
        await cfg.current_count.set(start)
        await cfg.last_user_id.set(None)

    async def _clear_pending_reset(self, guild: discord.Guild):
        """Clear persisted pending-reset state."""
        await self.config.guild(guild).pending_reset.set(False)
        await self.config.guild(guild).pending_reset_msg_id.set(None)
        self._pending_resets.pop(guild.id, None)

    async def _wait_for_reset_confirm(
        self,
        guild: discord.Guild,
        confirm_msg: discord.Message,
        restored: bool = False,
    ):
        """Wait for a ✅/❌ reaction on the confirmation message."""
        cfg = self.config.guild(guild)

        def check(reaction: discord.Reaction, user: discord.User):
            return (
                not user.bot
                and reaction.message.id == confirm_msg.id
                and str(reaction.emoji) in ("✅", "❌")
                and guild.get_member(user.id) is not None
                and guild.get_member(user.id).guild_permissions.manage_guild
            )

        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add", timeout=30.0, check=check
            )
            if str(reaction.emoji) == "✅":
                await self._reset_count(guild)
                start = await cfg.start_number()
                await confirm_msg.edit(
                    content=f"✅ Count has been reset to **{start}**."
                )
            else:
                await confirm_msg.edit(content="❌ Reset cancelled.")
        except asyncio.TimeoutError:
            await confirm_msg.edit(content="⏰ Reset confirmation timed out.")
        finally:
            try:
                await confirm_msg.clear_reactions()
            except discord.Forbidden:
                log.warning(
                    "Missing 'Manage Messages' permission to clear reactions in guild %s (%d).",
                    guild.name,
                    guild.id,
                )
            except discord.HTTPException as exc:
                log.warning("Failed to clear reactions: %s", exc)

            await self._clear_pending_reset(guild)

    # ------------------------------------------------------------------ #
    #  Listener                                                            #
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        cfg = self.config.guild(message.guild)

        if not await cfg.enabled():
            return

        channel_id = await cfg.channel_id()
        if not channel_id or message.channel.id != channel_id:
            return

        # Ignore command invocations
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        current_count = await cfg.current_count()
        last_user_id = await cfg.last_user_id()
        tick = await cfg.tick_reaction()
        wrong = await cfg.wrong_reaction()
        expected = current_count + 1

        # Try to parse the message as a number or math expression
        result = safe_eval(message.content)

        if result is None:
            # Not a number/math — delete it
            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass
            return

        # Check for same-user double-counting
        if message.author.id == last_user_id:
            await message.add_reaction(wrong)
            await message.channel.send(
                f"❌ **{message.author.display_name}**, you can't count twice in a row! "
                f"Chain broken at **{current_count}**. Restarting..."
            )
            await self._reset_count(message.guild)
            return

        # Check if the number is correct
        if abs(result - expected) < 1e-9:
            display = int(result) if result == int(result) else result
            await cfg.current_count.set(expected)
            await cfg.last_user_id.set(message.author.id)
            await message.add_reaction(tick)
            # Announce milestones (every 100)
            if expected % 100 == 0:
                await message.channel.send(
                    f"🎉 **{display}!** Nice work — keep it going!"
                )
        else:
            display = int(result) if result == int(result) else result
            await message.add_reaction(wrong)
            await message.channel.send(
                f"❌ **Wrong number!** You broke the chain at **{current_count}**. "
                f"Expected **{expected}**, got **{display}**. Restarting..."
            )
            await self._reset_count(message.guild)

    # ------------------------------------------------------------------ #
    #  Command Group                                                       #
    # ------------------------------------------------------------------ #

    @commands.group(name="counting", aliases=["count"])
    @commands.guild_only()
    async def counting_group(self, ctx: commands.Context):
        """Counting game commands."""

    # ---- enable/disable ------------------------------------------------

    @counting_group.command(name="enable")
    @checks.admin_or_permissions(manage_guild=True)
    async def counting_enable(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Enable counting in a channel.

        If no channel is provided, uses the current channel.

        Example: `[p]counting enable #counting`
        """
        channel = channel or ctx.channel
        cfg = self.config.guild(ctx.guild)
        await cfg.channel_id.set(channel.id)
        await cfg.enabled.set(True)
        start = await cfg.start_number()
        await cfg.current_count.set(start)
        await cfg.last_user_id.set(None)
        await ctx.send(
            f"✅ Counting enabled in {channel.mention}. Start counting from **{start + 1}**!"
        )

    @counting_group.command(name="disable")
    @checks.admin_or_permissions(manage_guild=True)
    async def counting_disable(self, ctx: commands.Context):
        """Disable the counting game."""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("🛑 Counting disabled.")

    # ---- reset ---------------------------------------------------------

    @counting_group.command(name="reset")
    @checks.admin_or_permissions(manage_guild=True)
    async def counting_reset(self, ctx: commands.Context):
        """Reset the count with a confirmation prompt."""
        guild_id = ctx.guild.id

        # Cancel any existing pending reset
        if guild_id in self._pending_resets:
            self._pending_resets[guild_id].cancel()
            del self._pending_resets[guild_id]
        await self._clear_pending_reset(ctx.guild)

        cfg = self.config.guild(ctx.guild)
        current = await cfg.current_count()
        start = await cfg.start_number()

        confirm_msg = await ctx.send(
            f"⚠️ Are you sure you want to reset the count from **{current}** back to **{start}**?\n"
            f"React with ✅ to confirm or ❌ to cancel. *(expires in 30s)*"
        )
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")

        # Persist so we can restore after a restart
        await cfg.pending_reset.set(True)
        await cfg.pending_reset_msg_id.set(confirm_msg.id)

        task = asyncio.create_task(self._wait_for_reset_confirm(ctx.guild, confirm_msg))
        self._pending_resets[guild_id] = task

    # ---- setstart ------------------------------------------------------

    @counting_group.command(name="setstart")
    @checks.admin_or_permissions(manage_guild=True)
    async def counting_setstart(self, ctx: commands.Context, number: int):
        """Set the starting number for the count.

        The count will begin at this number, and players count upward from `number + 1`.

        Example: `[p]counting setstart 0` → players count 1, 2, 3...
        Example: `[p]counting setstart 99` → players count 100, 101...
        """
        cfg = self.config.guild(ctx.guild)
        await cfg.start_number.set(number)
        await cfg.current_count.set(number)
        await cfg.last_user_id.set(None)
        await ctx.send(
            f"✅ Start number set to **{number}**. "
            f"The next expected count is **{number + 1}**."
        )

    # ---- setreaction ---------------------------------------------------

    @counting_group.command(name="setreaction")
    @checks.admin_or_permissions(manage_guild=True)
    async def counting_setreaction(
        self, ctx: commands.Context, reaction_type: str, emoji: str
    ):
        """Set the reaction emoji for correct or wrong counts.

        `reaction_type` must be `tick` (correct) or `wrong` (incorrect).

        Examples:
          `[p]counting setreaction tick ✅`
          `[p]counting setreaction wrong ❌`
          `[p]counting setreaction tick 🔥`
        """
        reaction_type = reaction_type.lower()
        if reaction_type not in ("tick", "wrong"):
            await ctx.send("❌ reaction_type must be `tick` or `wrong`.")
            return

        try:
            await ctx.message.add_reaction(emoji)
        except discord.HTTPException:
            await ctx.send(
                "❌ Invalid emoji. Make sure it's a standard Unicode emoji or a custom emoji from this server."
            )
            return

        cfg = self.config.guild(ctx.guild)
        if reaction_type == "tick":
            await cfg.tick_reaction.set(emoji)
            await ctx.send(f"✅ Correct-count reaction set to {emoji}.")
        else:
            await cfg.wrong_reaction.set(emoji)
            await ctx.send(f"✅ Wrong-count reaction set to {emoji}.")

    # ---- status --------------------------------------------------------

    @counting_group.command(name="status")
    async def counting_status(self, ctx: commands.Context):
        """Show the current counting game status."""
        cfg = self.config.guild(ctx.guild)
        enabled = await cfg.enabled()
        channel_id = await cfg.channel_id()
        current = await cfg.current_count()
        start = await cfg.start_number()
        tick = await cfg.tick_reaction()
        wrong = await cfg.wrong_reaction()
        last_uid = await cfg.last_user_id()
        pending = await cfg.pending_reset()

        channel_mention = f"<#{channel_id}>" if channel_id else "Not set"
        last_user = f"<@{last_uid}>" if last_uid else "Nobody yet"

        embed = discord.Embed(
            title="🔢 Counting Status",
            color=discord.Color.blurple() if enabled else discord.Color.red(),
        )
        embed.add_field(
            name="Status", value="✅ Enabled" if enabled else "🛑 Disabled", inline=True
        )
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Current Count", value=str(current), inline=True)
        embed.add_field(name="Next Expected", value=str(current + 1), inline=True)
        embed.add_field(name="Start Number", value=str(start), inline=True)
        embed.add_field(name="Last Counter", value=last_user, inline=True)
        embed.add_field(name="Correct Reaction", value=tick, inline=True)
        embed.add_field(name="Wrong Reaction", value=wrong, inline=True)
        if pending:
            embed.add_field(
                name="⚠️ Pending Reset", value="Awaiting confirmation", inline=False
            )

        await ctx.send(embed=embed)
