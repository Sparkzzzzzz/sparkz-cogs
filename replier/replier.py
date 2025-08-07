from redbot.core import commands
import discord


class Replier(commands.Cog):
    """Owner-only command to reply to a replied message with custom text."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="reply")
    @commands.is_owner()
    async def reply(self, ctx: commands.Context, *, text: str):
        """
        Reply to the message you're replying to, with the provided text.
        Only usable by the bot owner.
        """
        # Check if the command message is a reply
        if not ctx.message.reference or not ctx.message.reference.message_id:
            await ctx.send(
                "You must reply to a message to use this command.", delete_after=5
            )
            await ctx.message.delete()
            return

        # Fetch the original message that was replied to
        try:
            replied_msg = await ctx.channel.fetch_message(
                ctx.message.reference.message_id
            )
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await ctx.send("Couldn't fetch the replied message.", delete_after=5)
            await ctx.message.delete()
            return

        # Send the reply
        await replied_msg.reply(text)

        # Delete the command invocation message
        await ctx.message.delete()
