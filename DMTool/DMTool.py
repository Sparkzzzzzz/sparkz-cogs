import discord
from redbot.core import commands, checks
from redbot.core.bot import Red


class DMTool(commands.Cog):
    """Owner-only DM utilities."""

    def __init__(self, bot: Red):
        self.bot = bot

    # ---------------------------------------
    # SEND DM COMMAND
    # ---------------------------------------
    @commands.command(aliases=["senddm", "sdm"])
    @checks.is_owner()
    async def send_dm(self, ctx, user: discord.User, *, message: str):
        """Send a plaintext DM to a user."""
        try:
            await user.send(message)
        except discord.Forbidden:
            return await ctx.send("❌ I cannot DM this user.")

        embed = discord.Embed(
            title="DM Sent",
            description=f"Message sent to **{user}** (`{user.id}`)\n\n**Content:**\n{message}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    # ---------------------------------------
    # CLEAR DM COMMAND
    # ---------------------------------------
    @commands.command(aliases=["cleardm", "cdm"])
    @checks.is_owner()
    async def clear_dm(self, ctx, user: discord.User, count: int = None):
        """
        Delete bot-sent messages from a user's DM.
        If `count` is not provided → ask for confirmation to delete ALL.
        """

        # Fetch DM channel
        channel = user.dm_channel
        if channel is None:
            channel = await user.create_dm()

        # If a specific count is given -----------------------------------
        if count is not None:
            deleted = 0

            async for msg in channel.history(limit=200):
                if msg.author.id == self.bot.user.id:
                    try:
                        await msg.delete()
                        deleted += 1
                    except:
                        pass

                    if deleted >= count:
                        break

            embed = discord.Embed(
                title="DM Cleanup Complete",
                description=f"Deleted **{deleted}** messages from **{user}** (`{user.id}`).",
                color=discord.Color.green()
            )
            return await ctx.send(embed=embed)

        # No count provided → ask for full delete confirmation ------------
        confirm_embed = discord.Embed(
            title="Clear All DMs?",
            description=(
                f"Do you want to delete **ALL** bot-sent DMs with **{user}** (`{user.id}`)?\n\n"
                "React with:\n"
                "✔ to confirm\n"
                "✖ to cancel"
            ),
            color=discord.Color.orange()
        )
        confirm_msg = await ctx.send(embed=confirm_embed)

        check = "✔"
        cancel = "✖"

        await confirm_msg.add_reaction(check)
        await confirm_msg.add_reaction(cancel)

        def reaction_check(reaction, reactor):
            return (
                reactor == ctx.author
                and reaction.message.id == confirm_msg.id
                and str(reaction.emoji) in [check, cancel]
            )

        try:
            reaction, reactor = await self.bot.wait_for(
                "reaction_add", timeout=30.0, check=reaction_check
            )
        except TimeoutError:
            return await ctx.send("⌛ Timed out — no action taken.")

        # ✔ → Delete ALL bot messages
        if str(reaction.emoji) == check:
            deleted = 0
            async for msg in channel.history(limit=500):
                if msg.author.id == self.bot.user.id:
                    try:
                        await msg.delete()
                        deleted += 1
                    except:
                        pass

            return await ctx.send(
                f"🧹 Deleted **all ({deleted})** bot-sent DMs with **{user}**."
            )

        # ✖ → Cancel
        else:
            return await ctx.send("❌ Cancelled — no messages deleted.")


async def setup(bot: Red):
    await bot.add_cog(DMTool(bot))
