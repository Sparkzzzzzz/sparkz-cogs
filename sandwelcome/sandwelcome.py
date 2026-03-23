from redbot.core import commands
import discord

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


async def setup(bot):
    await bot.add_cog(SandWelcome(bot))
