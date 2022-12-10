import discord
from redbot.core import commands
import interactions

class Voting(commands.Cog):
    """Slash tag that sends a voting link when invoked."""

    def __init__(self, bot):
        self.bot = bot
        
    bot = interactions.Client

    @bot.command(
        name="vote",
        description="Vote for CeneVspeed Clan!",
        scope=916294593228714014,
    )

    async def vote(ctx: interactions.CommandContext):
        embed = discord.Embed(title="Vote for CeneVspeed Clan!", description="https://top.gg/servers/916294593228714014") #,color=Hex code
        embed.add_field(name="Perks:", value="")
        embed.add_field(name="", value="`>` Access to <#979594849273643048>")
        embed.add_field(name="", value="`>` Hoisted role!")
        embed.add_field(name="", value="`>` Access to <#952146169105104906>")
    
        interactions.response.send(embed=embed, ephemeral=True)