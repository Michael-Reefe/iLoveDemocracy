import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional
import datetime
import time
import copy
import asyncio
import numpy as np

import ui_elements
import rcv

# Replace these with your own guild ID and token
GUILD_ID = 123456789
TOKEN = 'your token here'

class Palpy(discord.Client):

    def __init__(self):
        intents = discord.Intents.default()
        intents.reactions = True
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
                # stop tasks that are updating the embed
                poll.message_update_loop.cancel()
                poll.disable_buttons()
                polls.pop(poll.name)
                del poll
                # send the results messages
                for oi in output:
                    await channel.send('```' + oi + '```', silent=True)
                    await asyncio.sleep(0.5)


client = Palpy()
polls = {}


# I hate this
@client.tree.command(guild=discord.Object(id=GUILD_ID), name='newpoll', description='Set up a new poll')
async def newpoll(interaction, name: str, choice1: str, choice2: Optional[str] = None,
                  choice3: Optional[str] = None, choice4: Optional[str] = None, choice5: Optional[str] = None,
                  choice6: Optional[str] = None, choice7: Optional[str] = None, choice8: Optional[str] = None,
                  choice9: Optional[str] = None, choice10: Optional[str] = None,
                  time_limit: Optional[float] = 24., description: Optional[str] = None,
                  winners: Optional[int] = 1):
    global polls
    c_all = [choice1, choice2, choice3, choice4, choice5, choice6, choice7, choice8, choice9, choice10]
    choices = []
    for c in c_all:
        if c is not None:
            choices.append(c)
    newpoll = Poll(interaction.user.id, interaction.channel, name, description, choices, n_winners=winners, timeout=time_limit*3600)
    polls[name] = newpoll
    await interaction.response.send_message(embed=newpoll.embed, view=newpoll.view)
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

    poll = polls[name]
    if interaction.user.id != poll.creator:
        await interaction.response.send_message('Only the creator of the poll can close it!', ephemeral=True)
        return

    print(f'Poll {name} has been manually closed. Printing results.')
    channel = poll.channel
    output = poll.run_election()
    poll.closed = True
    # stop tasks that are updating the embed
    poll.message_update_loop.cancel()
    poll.disable_buttons()
    polls.pop(name)
    del poll
    # send the results messages
    await interaction.response.send_message('```' + output[0] + '```')
    for oi in output[1:]:
        await channel.send('```' + oi + '```', silent=True)
        await asyncio.sleep(0.5)


class Poll:

    def __init__(self, creator, channel, poll_name='Generic Poll', description=None, 
                 poll_choices=None, n_winners=1, timeout=24*3600):
        self.creator = creator                                      # the user ID of whoever made the poll
        self.channel = channel                                      # channel the poll is in
        self.name = poll_name                                       # name of the poll
        self.choices = poll_choices                                 # initialize the choices/candidates
        self.ballots = np.zeros((len(poll_choices),0), dtype=int)   # initialize an array for the ballots
        self.voters = np.zeros((0,), dtype=int)                     # store user IDs for each voter
        self.n_votes = 0
        self.n_winners = n_winners                                  # how many winners the poll will have
        self.timeout = timeout                                      # poll time limit in seconds
        self.time0 = time.monotonic()                               # starting time of the poll
        self.closed = False                                         # if the poll is closed
        self.embed = None                                           # will hold the embed
        self.view = None                                            # will hold the view 

        notice = f'''\n
        To obtain your voting ballot for this poll, use the button at the bottom 
        of this message. The choices are listed below. This poll will have 
        {self.n_winners} winners.
        '''
        if description is None:
            description = f'''
            This is a ranked-choice (AKA alternative) voting poll! You will be able to rank
            each of the options in the poll from your 1st most preferred choice to your least
            preferred choice, and the end result will be calculated in a way that makes the
            most people happy as possible.''' 
        self.description = description + notice                              # description of the poll
        self.make_pretty_embed()
        self.make_button_view()
    
    def make_pretty_embed(self):
        embed = discord.Embed(title=self.name, description=self.description, color=discord.Color.from_str('#663399'),
                              timestamp=datetime.datetime.now())   # rebeccapurple
        places = ''
        for i in range(len(self.choices)):
            places += f'**0**   *{ui_elements.get_place_str(i+1)}-choice votes*\n'
        for i, choice in enumerate(self.choices):
            embed.add_field(name=choice, value=places, inline=True)
        embed.set_footer(text=f'{self.n_votes} voter(s)\nThis poll expires in {ui_elements.time_formatter(self.timeout)}')
        self.embed = embed
    
    @tasks.loop(seconds=10)
    async def message_update_loop(self, message):
        print('Updating poll embed expiry times')
        time1 = time.monotonic()
        dt = time1 - self.time0
        time_remaining = self.timeout - dt
        places = ['' for _ in range(len(self.choices))]
        for i in range(len(self.choices)):
            for j in range(len(self.choices)):
                current_votes = np.sum(self.ballots[j,:] == i+1)
                places[j] += f'**{current_votes}**   *{ui_elements.get_place_str(i+1)}-choice votes*\n'
        # update items
        for i, choice in enumerate(self.choices):
            self.embed.set_field_at(i, name=choice, value=places[i])
        # update footer
        self.embed = self.embed.set_footer(text=f'{self.n_votes} votes\nThis poll expires in {ui_elements.time_formatter(time_remaining)}')
        await message.edit(embed=self.embed)
    
    def make_button_view(self):
        self.view = discord.ui.View()
        ballot_btn = BallotButton(self.name)
        close_btn = CloseButton(self.name)
        self.view.add_item(ballot_btn)
        self.view.add_item(close_btn)
    
    def disable_buttons(self):
        for child in self.view.children:
            child.disabled = True

    def add_new_ballot(self, ballot, user_id):
        # check if the poll is still going
        time1 = time.monotonic()
        if time1 - self.time0 > self.timeout:
            self.closed = True
            return False
        if user_id in self.voters:
            return False
        ballot = ballot.reshape((len(ballot),1))
        self.ballots = np.concatenate((self.ballots, ballot), axis=1)
        self.voters = np.append(self.voters, user_id)
        self.n_votes += 1
        print(ballot)
        return True
    
    def run_election(self, quiet=False):
        # get the results of the poll
        output = rcv.run_election(self.choices, self.ballots, self.n_winners)
        if not quiet:
            print(output)
        return output


class BallotButton(discord.ui.Button):

    def __init__(self, poll_name):
        super().__init__(style=discord.ButtonStyle.blurple, label=f'Get your ballot!')
        self.poll_name = poll_name
    
    # simple callback function that calls get_ballot for the poll the button is associated with
    async def callback(self, interaction):
        await getballot.callback(interaction, self.poll_name)
    

class CloseButton(discord.ui.Button):

    def __init__(self, poll_name):
        super().__init__(style=discord.ButtonStyle.red, label=f'Close poll')
        self.poll_name = poll_name
    
    # simple callback that closes the poll if the user is the one who set up the poll
    async def callback(self, interaction):
        await closepoll.callback(interaction, self.poll_name)


client.run(TOKEN)
