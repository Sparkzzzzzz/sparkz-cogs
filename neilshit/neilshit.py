import discord
from discord import client
from redbot.core import commands
import random


class NeilShit(commands.Cog):
    """Neil is shit!"""

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

        if "Neil" in sentence:
            a = "Ew if you fucking used the word Neil in this sentence then I wont fucking dignify it with a response."
            await ctx.send(a)

        elif "neil" in sentence:
            a = "Ew if you fucking used the word Neil in this sentence then I wont fucking dignify it with a response."
            await ctx.send(a)

        elif "Sparkz" in sentence:
            b = "Sparkz is goated."
            await ctx.send(b)

        elif "sparkz" in sentence:
            b = "Sparkz is goated."
            await ctx.send(b)

        elif "Hridaan" in sentence:
            c = "Hridaan is goated."
            await ctx.send(c)

        elif "hridaan" in sentence:
            c = "Hridaan is goated."
            await ctx.send(c)

        else:
            response = random.choice(responses)
            await ctx.send(response)