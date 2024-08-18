import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional
import datetime
import time
import copy
import numpy as np

import ui_elements
import rcv

# Replace these with your own guild ID and token
GUILD_ID = 123456789
TOKEN = 'your token here'

class Palpy(discord.Client):

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.synced = False
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await self.tree.sync(guild=discord.Object(id=GUILD_ID))
            self.synced = True
        print(f'Bot has logged in as {self.user}')
    
    # Start the background task 
    async def setup_hook(self):
        self.check_poll_results.start()

    # background task: check if any polls have been closed and print the results
    @tasks.loop(seconds=60)
    async def check_poll_results(self):
        global polls
        time1 = time.monotonic()
        print('Checking for closed polls')
        d2 = polls.copy()
        for poll in d2.values():
            channel = copy.copy(poll.channel)
            dt = time1 - poll.time0
            time_remaining = poll.timeout - dt
            if time_remaining <= 0: 
                print(f'Poll {poll.name} has expired. Printing results.')
                # poll has expired - run the results 
                output = poll.run_election()
                poll.closed = True
                poll.message_update_loop.cancel()
                polls.pop(poll.name)
                del poll
                # stop tasks that are updating the embed
                await channel.send('```' + output + '```')

client = Palpy()
polls = {}


@client.tree.command(guild=discord.Object(id=GUILD_ID), name='newpoll', description='Set up a new poll')
# I hate this
async def newpoll(interaction, name: str, choice1: str, choice2: Optional[str] = None,
                  choice3: Optional[str] = None, choice4: Optional[str] = None, choice5: Optional[str] = None,
                  choice6: Optional[str] = None, choice7: Optional[str] = None, choice8: Optional[str] = None,
                  choice9: Optional[str] = None, choice10: Optional[str] = None,
                  time_limit: Optional[float] = 24., description: Optional[str] = None):
    global polls
    c_all = [choice1, choice2, choice3, choice4, choice5, choice6, choice7, choice8, choice9, choice10]
    choices = []
    for c in c_all:
        if c is not None:
            choices.append(c)
    newpoll = ui_elements.Poll(interaction.channel, name, description, choices, timeout=time_limit*3600)
    polls[name] = newpoll
    await interaction.response.send_message(embed=newpoll.embed)
    message = await interaction.original_response()
    newpoll.message_update_loop.start(message)
    
@client.tree.command(guild=discord.Object(id=GUILD_ID), name='getballot', description='Get a ballot for the poll')
async def getballot(interaction, name: str):

    # Get the poll we want a ballot for
    poll = polls[name]

    # Keep track of the user who requested a ballot - only one per user!
    if interaction.user.id in poll.voters:
        await interaction.response.send_message("Sorry, you've already voted in this poll. Only one ballot per person!", ephemeral=True)
        return

    ballot_view = ui_elements.BallotView(n=len(poll.choices), poll=poll, choices=poll.choices)

    description = f"""
    **{poll.name}**:

    Please rank your choices using the following drop-down menus, 
    starting from your first (most favorable) choice. You can fill 
    in as many rankings as you see fit, whether that be only your 
    first choice, or all of your top choices. Due to discord 
    limitations, the maximum number of rankings you can specify at 
    the moment is 4, even if the number of options is larger than 4.

    When finished, please submit using the submit button. 
    The poll results are tracked in real time on the embed
    shown during the poll's creation. After the time limit is up, 
    the poll results will be announced in a separate message.\n
    """

    await interaction.response.send_message(description, view=ballot_view, ephemeral=True)

@client.tree.command(guild=discord.Object(id=GUILD_ID), name='closepoll', description='Manually close a poll')
async def closepoll(interaction, name: str):
    print(f'Poll {name} has been manually closed. Printing results.')
    poll = polls[name]
    output = poll.run_election()
    poll.closed = True
    poll.message_update_loop.cancel()
    polls.pop(name)
    del poll
    # stop tasks that are updating the embed
    await interaction.response.send_message('```' + output + '```')

client.run(TOKEN)
