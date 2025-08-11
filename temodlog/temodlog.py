import json
from pathlib import Path
from redbot.core import commands

from .eventmixin import EventMixin

# Load EUD statement if exists
try:
    with open(Path(__file__).parent / "info.json") as fp:
        __red_end_user_data_statement__ = json.load(fp).get("end_user_data_statement")
except Exception:
    __red_end_user_data_statement__ = ""


class TeModLog(EventMixin, commands.Cog):
    """Extended ModLog (Trusted Fork)"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__(bot)

    @commands.group(name="temodlog", invoke_without_command=True)
    @commands.bot_has_permissions(manage_guild=True)
    async def temodlog(self, ctx):
        """Manage TeModLog settings."""
        await ctx.send_help(ctx.command)
