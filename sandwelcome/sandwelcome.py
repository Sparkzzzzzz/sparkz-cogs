from redbot.core import commands
import discord
from discord import MessageType

ROLE_WELCOME_ID = 1196441293883199508
ROLE_WELCOME_CHANNEL_ID = 1196222261305286809


class SandWelcome(commands.Cog):
    """Manual + Role-based welcome system"""

    def __init__(self, bot):
        self.bot = bot

    # ------------------ Manual Command ------------------ #
    @commands.command()
    async def welcome(self, ctx, user: discord.Member):
        embed = discord.Embed(
            description=(
                "## Welcome to the Sand Tribes! Here's how to get started:\n"
                "`1.` Read the rules in <#1195856894993104926>\n"
                "`2.` Read the tribe laws in <#1296945197615153193>\n"
                "`3.` Check out our ranks in <#1195866718241824801>\n"
                "`4.` Apply for a tribe in <#1221375576582131816>\n"
                "`5.` Check out our custom tribe language in <#1297322838662844416>\n"
                "`6.` Optionally apply for the military in <#1221375732698320926>\n\n"
                "# And finally, enjoy! <:lilruuk:1226892886445129820>"
            ),
            color=0xB58B00,
        )
        embed.set_footer(text="Sent by the amazing Shark Bot!")

        await ctx.send(f"Welcome **{user.display_name}**!", embed=embed)

    # ------------------ Role-based Auto Welcome ------------------ #
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild

        target_role = guild.get_role(ROLE_WELCOME_ID)
        welcome_channel = guild.get_channel(ROLE_WELCOME_CHANNEL_ID)

        if not target_role or not welcome_channel:
            return

        if target_role not in before.roles and target_role in after.roles:
            embed = discord.Embed(
                description=(
                    "## Welcome to the Sand Tribes! Here's how to get started:\n"
                    "`1.` Read the rules in <#1195856894993104926>\n"
                    "`2.` Read the tribe laws in <#1296945197615153193>\n"
                    "`3.` Check out our ranks in <#1195866718241824801>\n"
                    "`4.` Apply for a tribe in <#1221375576582131816>\n"
                    "`5.` Check out our custom tribe language in <#1297322838662844416>\n"
                    "`6.` Optionally apply for the military in <#1221375732698320926>\n\n"
                    "# And finally, enjoy! <:lilruuk:1226892886445129820>"
                ),
                color=0xB58B00,
            )
            embed.set_footer(text="Sent by the amazing Shark Bot!")

            await welcome_channel.send(f"Welcome, {after.mention}!", embed=embed)

    @commands.command()
    @commands.has_role(1307731573927317625)
    async def catchupwelcomes(self, ctx):
        """Sends missed welcome messages based on join logs"""

        channel = ctx.guild.get_channel(1195856838843969656)

        # Get last bot message
        last_bot_message = None
        async for message in channel.history(limit=200):
            if message.author == self.bot.user:
                last_bot_message = message
                break

        members_to_welcome = []

        async for message in channel.history(
            after=last_bot_message.created_at if last_bot_message else None,
            limit=200
        ):
            if message.type == MessageType.new_member:
                member = message.author
                if member and not member.bot and member not in members_to_welcome:
                    members_to_welcome.append(member)

        if not members_to_welcome:
            await ctx.send("No missed welcomes found.")
            return

        for member in members_to_welcome:
            embed = discord.Embed(
                title=f"Bayarlaakhaa {member.display_name}!",
                description="The Khaars and the Ondokhaar welcome you to the desert with open arms.",
                color=0xFFD700,
            )
            embed.set_image(
                url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExczF5Zjh6ZTNqZ3h4dXQ2MjZyYWlrNHk1N2Nwc2Z2aHdzY2Roc3F1aiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/7A6FyTLMQ3xlI0ex4L/giphy.gif"
            )
            embed.set_footer(text="Sent by Shark Bot")

            await channel.send(f"Welcome, {member.mention}!", embed=embed)

        await ctx.send(f"✅ Sent {len(members_to_welcome)} missed welcomes.")


async def setup(bot):
    await bot.add_cog(SandWelcome(bot))
