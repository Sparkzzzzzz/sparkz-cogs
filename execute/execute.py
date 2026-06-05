import discord
from redbot.core import commands
from redbot.core.bot import Red
import traceback


class Execute(commands.Cog):
    """Execute multiple bot commands at once from a code block."""

    def __init__(self, bot: Red):
        self.bot = bot

    @commands.command(name="execute")
    @commands.is_owner()
    async def execute(self, ctx: commands.Context, *, block: str = None):
        """
        Execute multiple commands listed in a code block, in order.

        Usage:
        [p]execute
        ```
        help
        say hi
        welcomeset channel #general
        d?say hi
        ```

        - Lines without a prefix use the bot's current prefix.
        - Lines with a different prefix (e.g. d?) are sent as-is and treated as foreign bot commands (they'll be noted as unexecutable).
        - Errors and unknown commands are reported at the end.
        """
        # Extract content from code block if present
        raw = ctx.message.content

        # Find the code block in the original message
        if "```" in raw:
            start = raw.find("```") + 3
            # Skip language tag if present (e.g. ```python)
            if raw[start] != "\n":
                start = raw.find("\n", start) + 1
            end = raw.rfind("```")
            block_content = raw[start:end].strip()
        elif block:
            block_content = block.strip()
        else:
            await ctx.send(
                f"Please provide commands in a code block.\n"
                f"Usage: `{ctx.clean_prefix}execute` followed by a code block."
            )
            return

        lines = [line.strip() for line in block_content.splitlines() if line.strip()]

        if not lines:
            await ctx.send("No commands found in the code block.")
            return

        # Get all valid prefixes for this guild
        bot_prefixes = await self.bot.get_valid_prefixes(ctx.guild)

        errors = []
        success_count = 0

        status_msg = await ctx.send(f"⏳ Executing `{len(lines)}` command(s)...")

        for line in lines:
            # Determine if line starts with a known bot prefix
            matched_prefix = None
            for prefix in sorted(bot_prefixes, key=len, reverse=True):
                if line.startswith(prefix):
                    matched_prefix = prefix
                    break

            if matched_prefix is None:
                # Check if it starts with any prefix-like character that isn't ours
                # Heuristic: if starts with a non-alphanumeric char that's not our prefix, it's foreign
                if line[0] in "!?$%^&./\\;,~@#" or (len(line) > 1 and line[1] in "?!"):
                    errors.append(
                        (line, "Command uses a foreign/unknown prefix — skipped.")
                    )
                    continue
                # Otherwise treat as a command without prefix
                full_command = f"{bot_prefixes[0]}{line}"
            else:
                full_command = line

            # Build a fake message to invoke the command
            fake_message = ctx.message
            # We'll use copy context trick
            try:
                msg = ctx.message
                # Create a new Message-like object by monkeypatching content
                new_msg = discord.Message.__new__(discord.Message)
                new_msg.__dict__.update(msg.__dict__)
                new_msg.content = full_command

                new_ctx = await self.bot.get_context(new_msg)

                if new_ctx.command is None:
                    errors.append((line, "Command not found."))
                    continue

                # Check if bot can run the command (basic checks)
                try:
                    can_run = await new_ctx.command.can_run(
                        new_ctx, check_all_parents=True
                    )
                except commands.CommandError as e:
                    errors.append((line, f"Permission check failed: {e}"))
                    continue

                await self.bot.invoke(new_ctx)

                if new_ctx.command_failed:
                    errors.append((line, "Command raised an error during execution."))
                else:
                    success_count += 1

            except Exception as e:
                tb = traceback.format_exc()
                errors.append((line, f"Exception: {e}"))

        # Build result report
        lines_out = [
            f"✅ **{success_count}/{len(lines)} command(s) executed successfully.**"
        ]

        if errors:
            lines_out.append(f"\n⚠️ **{len(errors)} issue(s):**")
            for cmd_line, reason in errors:
                lines_out.append(f"• `{cmd_line}` — {reason}")

        report = "\n".join(lines_out)

        # Edit or send depending on length
        if len(report) <= 2000:
            await status_msg.edit(content=report)
        else:
            await status_msg.edit(
                content=f"✅ {success_count}/{len(lines)} succeeded. Errors below:"
            )
            # Chunk errors
            chunk = []
            for cmd_line, reason in errors:
                chunk.append(f"• `{cmd_line}` — {reason}")
                if len("\n".join(chunk)) > 1800:
                    await ctx.send("\n".join(chunk))
                    chunk = []
            if chunk:
                await ctx.send("\n".join(chunk))


async def setup(bot: Red):
    await bot.add_cog(Execute(bot))
