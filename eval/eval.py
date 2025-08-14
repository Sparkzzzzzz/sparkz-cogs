import discord
import traceback
import textwrap
import io
import contextlib
from redbot.core import commands
from redbot.core.bot import Red


class Eval(commands.Cog):
    """Owner-only Python evaluator."""

    def __init__(self, bot: Red):
        self.bot = bot

    @commands.is_owner()
    @commands.command(name="eval")
    async def _eval(self, ctx: commands.Context, *, code: str):
        """Evaluate Python code."""
        # Remove code block formatting if provided
        if code.startswith("```") and code.endswith("```"):
            code = "\n".join(code.split("\n")[1:-1])

        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self.bot,
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
        result = f"{value}{ret if ret is not None else ''}"

        if len(result) == 0:
            result = "✅ No output."

        if len(result) > 1900:
            await ctx.send("Output too long, sending as file.")
            return await ctx.send(
                file=discord.File(io.BytesIO(result.encode()), filename="output.txt")
            )

        await ctx.send(f"```py\n{result}\n```")
