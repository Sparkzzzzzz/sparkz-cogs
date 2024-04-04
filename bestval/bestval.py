import discord
from discord import client
from redbot.core import commands
import random


class BestVal(commands.Cog):
    """Best Valletta?"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def eball(self, ctx, *, sentence):
        """Ask a question!"""

        responses = [
            "It is certain.",
            "It is decidedly so.",
            "Without a doubt.",
            "Yes – definitely.",
            "You may rely on it.",
            "As I see it, yes.",
            "Most likely.",
            "Outlook good.",
            "Yes.",
            "Signs point to yes.",
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful.",
        ]

        if "Who is the best Valletta?" in sentence:
            a = "Cyrus is the best Valletta in existence."
            await ctx.channel.send(a)

        if "Who's the best Valletta?" in sentence:
            d = "Cyrus is the best Valletta in existence."
            await ctx.channel.send(d)

        elif "Cyrus" in sentence:
            b = "Lord Cyrus is the best."
            await ctx.channel.send(b)

        elif "syrus" in sentence:
            c = "Lord Cyrus is the best."
            await ctx.channel.send(c)

        else:
            response = random.choice(responses)
            await ctx.channel.send(response)
