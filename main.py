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
async def newpoll(interaction, name: str, choice1: str, choice2: Optional[str] = None,
                  choice3: Optional[str] = None, choice4: Optional[str] = None, choice5: Optional[str] = None,
                  time_limit: Optional[float] = 24., description: Optional[str] = None):
    global polls
    c_all = [choice1, choice2, choice3, choice4, choice5]
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
    {poll.name}:\n
    Please rank your choices using the following buttons. Click the button in each row that 
    corresponds to the ranking that you want for the item in that row. You can only use each
    ranking once.
    1 = Most favorable
    {ballot_view.n} = Least favorable\n
    At the very least, you must pick your first choice. Everything after that is optional.\n
    When finished, please submit using the submit button.\n
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
