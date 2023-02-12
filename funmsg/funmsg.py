import discord
import os
import random
import datetime
import asyncio
import aiohttp
import math
import requests
import time
import pytz
from redbot.core import commands

class FunMsg(commands.Cog):
    """Sends a random conversation initiating topic when invoked!"""

    def __init__(self, bot):
        self.bot = bot

    intents = discord.Intents.all()
    intents.members = True
    intents.reactions = True

    client = commands.Bot(command_prefix='.', intents=intents)


    DefaultClearAmmount = 5
    cooldown = 5
    triggerMessageCount = 10
    triggerDuration = 60

    disabled = "False"
    i = 0


    options = ["If you could be any animal, what animal would you be?", "What is your biggest pet peeve?", "Where would you like to go to on your next vacation?", "What's the craziest thing that you've ever done?", "What is something that you can't live without?", "What are some signs that someone is lying to you?", "If you could s one age for the rest of your life, what age would you pick?", "What do you like to do for fun?", "What is your favorite activity to do on vacation?", "If you were a superhero, what would your superpower be and what name would you give yourself?", "What is your worst habbit?", "Describe what your dream home would look like.", "How long can you go without looking at your phone?", "What is the weirdest thing that you have eaten?", "What would you like carved on your tombstone when you die?", "If you could live anywhere in the world, where would you live?", "What are some things that you should not say at a funeral?", "Tell me about an embarrassing moment.", "Toilet seat up or toilet seat down?", "Is it more acceptable to fart in front of strangers or people you know?", "Do men have it better in life than women?", "What would you do if you really had to use the bathroom at a restaurant, but all the toilets were out of order?", "Give me some bad first date advice.", "What is your worst habit?", "What are some things that you should not say to a police officer?", "Toilet paper over or under?", "What is the worst gift you could give to a newly married couple?", "What do you do when you have to pick your nose, but you're not at home?", "What are some things that you might be thinking but shouldn't say after a long trip with your significant other?", "What are your biggest pet peeves?", "What is the longest that you've gone without showering/bathing?", "What are some things that you should not not say during a job interview?", "Where is the worst place to go on a first date?", "Is it ok to pee in the shower?", "What is the best pickup line that you know of?", "Do attractive people have easier lives?", "What long term goals have you made for yourself?", "Is it better to be told comforting lies or unpleasant truths?", "What are some of the best books that you have read?", "Is it better to dream big and not live up to expectations or have low expectations and exceed them?", "What motivates you?", "If you could give one piece of advice to the whole world, what would it be?", "If money were not an issue, what would you be doing with your life?", "What do you worry about the most?", "What do you consider your greatest achievement?", "If you could live in any time period, in any culture, which period would you choose?", "What was the best part of your week?", "Do you have any brothers or sisters?", "Names?", "Older or younger?", "Do you have any pets?", "What are their names?", "Who takes care of them?", "Where does your mom/dad work?", "What do they do?", "What is your favorite food?", "What do you want to be when you grow up?", "What do you spend your allowance/money on?", "If you could have any super power, what would it be?", "Where do you go to school?", "Do you like school?", "What grade are you in?", "What's your favorite part of school?", "What do you like least about school?", "What is your best subject?", "What do you do after you get home from school?", "What is your favorite thing to do on weekends?", "Do you play any sports?", "What is your favorite TV show?", "What is your favorite movie?", "What is your favorite book?", "Who is your best friend?", "At what age would you consider someone to be old?", "If you were given three wishes, what would you wish for?", "What makes a good leader?", "What makes a poor leader?", "Are leaders born or made?", "What are some common leadership mistakes?", "What should the relationship between a leader and follower be like?", "What is the most difficult aspect of being a leader?", "What's the most important thing to look for in a good leader?", "How do you measure how the success of a leader?", "What is the biggest difference between a leader and a follower?", "What is the best way to deliver bad news to a team?", "Do you think anyone can be a leader?", "What areas do well on as a leader leader?", "What areas do you need to work on as a leader?", "Tell me a time when you displayed leadership skills.", "What is your style of leadership?", "Describe a time when you failed and how you handled it.", "What's the best way to delegate responsibilities among your team?", "How do you decide on what the best direction for your team is?", "What motivates you?", "How do you motivate others to accomplish a common goal?", "How do you deal with people who have conflicting opinions from you?", "What is the best way to get others to accept your point of view?", "What are the benefits of owning your own business versus working for someone else?", "Is it more important to reinvest money into improving and growing the business or to maintain a high profit margin?", "What businesses have long term staying power?", "What's more important, good customer service or the quality of your product/service?", "Would you rather sell many things at a lower price or fewer things at a higher price?", "What company(s) do you admire and why?", "What're the keys to running a successful business?", "Why do so many businesses fail?", "Is it better to enter into a business that has a lot of competition, where you know there's a big market or enter into a smaller market that is less competitive?", "How important is it to have a business plan?", "How much of an impact does technology have on businesses?", "Is it better to start a business that addresses something that you're passionate about or see a big profit potential?", "What are the most important things to look for when hiring an employee?", "What kind of business do you want to start?", "Where is your business going to be located?", "How much money do you need to start up your business?", "How will you finance your business?", "What are you willing to sacrifice/invest into your business?", "Would having a partner be benefit to you?", "What skills and knowledge do I need to learn before opening your business?", "Do you want to buy an existing business or start a brand new business?", "Does your family and friends support your decision to go into business?", "What is your competitive advantage going to be?", "How will you market your business?", "Who is my target customer?", "What permits, certifications, and licenses do I need to get before opening up my own business?", "Who will your competition be?", "How many employees will I need?", "How will you price your products or services?", "What will your business name be?", "What should be done to increase the quality level of education?", "Are private schools better than public schools?", "Do you think a formal education is necessary to be successful today?", "How important are you grades to you?", "Do you enjoy going to school?", "What was your favorite subject? Why?", "What was your least favorite subject? Why?", "Who was your most memorable teacher?", "What are the best teaching methods?", "What makes a good teacher good?", "What type of person makes the best student?", "Do you procrastinate on your school work? Why?", "What are the benefits and drawbacks of having school uniforms?", "Do you think teachers deserve to be paid more?", "What are the positives and negatives of being home schooled?", "What is the best way to motivate a student to learn?", "How important is homework to getting a good education?", "What is the most important subject?", "What is the least important subject?", "How well do grades measure how much a student has actually learned?", "What are the benefits/drawbacks to online classes?", "How important do you think getting a college degree is?", "What did you study in college?", "How is college different than high school?", "How important is it to go to a college with a well known name?", "Does college prepare you for 'real life'?", "Are you closer to your family or friends?", "How important is your family to you?", "Is it better to be a single child or to have lots of siblings?", "How well do you get along with your family members?", "Who is your favorite member of your family?", "How similar are you to your parents?", "Who is the weirdest member of your family?", "How big of a family do you have?", "How often do you get together with your family?", "What was growing up in your family like?", "What is the most important lesson that you have learned from your parents?", "What is your favorite meal of the day?", "Do you prefer to eat at a restaurants or have a home cooked meal?", "Do you think about where your food comes from?", "What is your favorite type of food?", "What do you usually drink with your meals?", "Do you watch what you eat?", "What is your usual tipping practice at a restaurant?", "Do you like to cook?", "How often do you eat?", "How long do you usually take to eat?", "Where is your favorite place to eat?", "What do you normally eat for breakfast?", "Do you pay attention to the nutritional value of things you eat?", "What is love?", "Who do you love?", "Do you believe there are different types of love? If so, what types of love are there?", "Why do people fall in love?", "Do you believe in love at first sight?", "What are some of the pros and cons of being in love?", "Do you believe that love conquers all?", "How are attraction and love different?", "Do you think it's possible to fall out of love?", "What are some ways that you can show love?", "What is your favorite romantic movie?", "What is your favorite love song?", "What qualities are important for you in a partner?", "Describe your ideal date.", "Would you ever go on a blind date?", "How do you know when a relationship is getting serious?", "Do you believe in marriage?", "Do you believe in arranged marriages?", "Is it better to be single or married?", "What do you think the ideal age to get married is?", "How long after dating someone will it take for you to know if they are marriage material?", "Describe your ideal wedding.", "What do you think the secret to a happy marriage is?", "How big of a role does money play in determining one's happiness?", "Are you a saver or a spender?", "How much money does the average person need to to retire?", "Can money buy happiness?", "Are you saving up for anything?", "What do you spend your money on?", "If you won a million dollars, what would you do with it?", "How many credit cards do you have?", "Do you invest your money?", "Do you believe in playing the lottery?", "Would you ever lend a significant amount of money to a friend?", "What is the most valuable thing that you own?", "Do you believe that the best things in life are free?", "Is there such a thing as having too much money?", "Does having a lot of money change people?", "Do you think taxes should be higher?", "What is your biggest monthly expense?", "Are the poor more generous than the rich?", "Do you ever buy things that you don't really need because it's cheap?", "What do you like to do in your free time?", "Do you have any hobbies?", "What do you usually do on weekends?", "How often do you exercise?", "What motivates you to exercise?", "What does your exercise routine consist of?", "Do you prefer to stay in or go out and watch a movie?", "Who is your favorite actor/actress?", "What is the worst movie that you ever saw?", "Do you read reviews about a movie before deciding whether to watch it or not?", "What was the last movie that you saw?", "What is your favorite movie?", "What is the most number of times have you watched the same movie?", "How often do you read?", "What genre of books do you like to read?", "What are your favorite books?", "Has reading a book ever changed your life?", "Do you have a favorite author?", "Do you play or watch any sports?", "How often do you play your sport?", "If you had the ability, would you have become a professional athlete?", "What is your favorite sports team?", "What TV shows are you currently following?", "What is your favorite TV series of all time?", "How many hours a week do you spend watching TV?", "Do you multi-task while watching TV?", "Do you play any video games?", "How many hours a week do you spend playing video games?", "What games do you like to play?", "Is it better to work at a job that you love or a job that pays well?", "Tell me how a typical day at work is like for you.", "Do you like the work that you do?", "What is your favorite thing about your job?", "What do you like least about your job?", "What are your coworkers like?", "What is your dream job?", "What is your boss like?", "Where do you see yourself in 5 years?", "If you were the owner of the business where you work, what would you do to improve it?", "Which is better, being the boss or an employee?", "What was your first job?", "How did you get your current job?", "When you were younger, what did you want to do when you grew up?"]

    async def mainloop():
        while True:
            await asyncio.sleep(triggerDuration)
            i = 0


    @client.event
    async def on_ready():
        await mainloop()

    def move_to_end(list, elem):
        list = [x for x in list if x != elem] + [elem]
        return list


    async def sendRandom(channel):

        options = options

        selectionIndex = 0.05
        firstItems = options[0:math.ceil((len(options) * selectionIndex))]
        print(firstItems)

        selectedItem = random.randint(0, len(firstItems))
        print(selectedItem)
        embed = discord.Embed(title="Here's a topic!",
                            color=discord.Color.orange(),
                            description=firstItems[selectedItem])
        await client.get_channel(channel).send(embed=embed)

        # Shuffle the list
        random.shuffle(options)

        # Move the used item to the end of list
        newList = move_to_end(options, firstItems[selectedItem])

        # Save new data to database

        options = newList


    #setup


    async def startCooldown():

        global disabled

        disabled = "True"
        await asyncio.sleep(cooldown)
        disabled = "False"


    @client.event
    async def on_message(message):

        global disabled
        global i

        if disabled == "True":
            return

        i = i + 1
        print(i)
        if i == triggerMessageCount:
            i = 0
            print("triggered")
            await sendRandom(message.channel.id)
            await startCooldown()


    async def reset():
        await asyncio.sleep(triggerDuration)
        global i
        i = 0