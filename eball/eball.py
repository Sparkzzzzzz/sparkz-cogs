import discord
from discord import client
from redbot.core import commands
import random

class _8ball(commands.Cog):
    """Owner only custom commands!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='8ball', description='Let the 8 Ball Predict!\n')
    async def _8ball(self, ctx, question):
        responses = ['As I see it, yes.',
                'Yes.',
                'Positive',
                'From my point of view, yes',
                'Convinced.',
                'Most Likley.',
                'Chances High',
                'No.',
                'Negative.',
                'Not Convinced.',
                'Perhaps.',
                'Not Sure',
                'Mayby',
                'I cannot predict now.',
                'Im to lazy to predict.',
                'I am tired. *proceeds with sleeping*']
        response = random.choice(responses)
        embed=discord.Embed(title="The Magic 8 Ball has Spoken!")
        embed.add_field(name='Question: ', value=f'{question}', inline=True)
        embed.add_field(name='Answer: ', value=f'{response}', inline=False)
        await ctx.send(embed=embed)
    
        
    