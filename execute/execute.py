import copy
import discord
from redbot.core import commands
from redbot.core.bot import Red


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
        ```
        """
        raw = ctx.message.content

        if "```" in raw:
            start = raw.find("```") + 3
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

        bot_prefixes = await self.bot.get_valid_prefixes(ctx.guild)

        errors = []
        success_count = 0

        status_msg = await ctx.send(f"⏳ Executing `{len(lines)}` command(s)...")

        for line in lines:
            # Check if line starts with a known bot prefix
            matched_prefix = None
            for prefix in sorted(bot_prefixes, key=len, reverse=True):
                if line.startswith(prefix):
                    matched_prefix = prefix
                    break

            if matched_prefix is None:
                # Likely a foreign bot prefix
                if line and not line[0].isalnum():
                    errors.append(
                        (line, "Command uses a foreign/unknown prefix — skipped.")
                    )
                    continue
                full_command = f"{bot_prefixes[0]}{line}"
            else:
                full_command = line

            try:
                # copy.copy gives a shallow copy of the Message object
                # then we just override .content — works without touching internals
                new_msg = copy.copy(ctx.message)
                new_msg.content = full_command

                new_ctx = await self.bot.get_context(new_msg)

                if new_ctx.command is None:
                    errors.append((line, "Command not found."))
                    continue

                try:
                    await new_ctx.command.can_run(new_ctx, check_all_parents=True)
                except commands.CommandError as e:
                    errors.append((line, f"Permission check failed: {e}"))
                    continue

                await self.bot.invoke(new_ctx)

                if new_ctx.command_failed:
                    errors.append((line, "Command raised an error during execution."))
                else:
                    success_count += 1

            except Exception as e:
                errors.append((line, f"Exception: {e}"))

        lines_out = [
            f"✅ **{success_count}/{len(lines)} command(s) executed successfully.**"
        ]

        if errors:
            lines_out.append(f"\n⚠️ **{len(errors)} issue(s):**")
            for cmd_line, reason in errors:
                lines_out.append(f"• `{cmd_line}` — {reason}")

        report = "\n".join(lines_out)

        if len(report) <= 2000:
            await status_msg.edit(content=report)
        else:
            await status_msg.edit(
                content=f"✅ {success_count}/{len(lines)} succeeded. Errors below:"
            )
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
