import discord
import traceback
import textwrap
import io
import contextlib
import asyncio
from redbot.core import commands
from redbot.core.bot import Red


class Eval(commands.Cog):
    """Owner-only Python evaluator with file, input(), and math support."""

    def __init__(self, bot: Red):
        self.bot = bot

    async def _get_input(self, ctx, prompt=""):
        """Wait for the author to respond in the same channel."""
        if prompt:
            await ctx.send(f"📥 {prompt}")
        else:
            await ctx.send("📥 Input:")

        try:
            msg = await self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                timeout=60,
            )
            return msg.content
        except asyncio.TimeoutError:
            await ctx.send("⌛ Input timed out.")
            raise

    @commands.is_owner()
    @commands.command(name="eval")
    async def _eval(self, ctx: commands.Context, *, code: str = None):
        """Evaluate Python code or math expressions, supports files and input()."""

        # Handle file attachment
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            if not attachment.filename.endswith(".py"):
                return await ctx.send("❌ Only `.py` files are supported.")
            file_bytes = await attachment.read()
            code = file_bytes.decode("utf-8")

        if not code:
            return await ctx.send(
                "❌ You must provide Python code or attach a `.py` file."
            )

        # Remove code block formatting
        if code.startswith("```") and code.endswith("```"):
            code = "\n".join(code.split("\n")[1:-1])

        # Math-only quick eval
        if "\n" not in code and all(ch in "0123456789+-*/().% " for ch in code.strip()):
            try:
                result = eval(code, {"__builtins__": {}})
                return await ctx.send(f"```py\n{result}\n```")
            except Exception as e:
                return await ctx.send(f"```py\nError: {e}\n```")

        # Custom async input function
        async def async_input(prompt=""):
            return await self._get_input(ctx, prompt)

        # Sync wrapper for input() so user can call it like normal
        loop = asyncio.get_running_loop()

        def sync_input(prompt=""):
            fut = asyncio.run_coroutine_threadsafe(async_input(prompt), loop)
            return fut.result()

        # Prepare execution environment
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self.bot,
            "input": sync_input,  # override input
            "__builtins__": __builtins__,  # keep builtins available
        }

        stdout = io.StringIO()
        code = f"async def func():\n{textwrap.indent(code, '    ')}"

        try:
            exec(code, env)
        except Exception as e:
            return await ctx.send(f"```py\nError compiling:\n{e}\n```")

        func = env["func"]
        try:
            with contextlib.redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            err = traceback.format_exc()
            return await ctx.send(f"```py\n{value}{err}\n```")

        value = stdout.getvalue()
        result = f"{value}{repr(ret) if ret is not None else ''}"

        if len(result) == 0:
            result = "✅ No output."

        if len(result) > 1900:
            await ctx.send("Output too long, sending as file.")
            return await ctx.send(
                file=discord.File(io.BytesIO(result.encode()), filename="output.txt")
            )

        await ctx.send(f"```py\n{result}\n```")
