from typing import Optional
import datetime
import time
import asyncio
import logging
import logging.handlers

import numpy as np
import discord
from discord import app_commands
from discord.ext import tasks

import ui_elements
import rcv
import star

# make a separate 'info.txt' file with your 
# token on the first line
with open('info.txt', 'r') as file:
    TOKEN = file.readline()

# set up basic logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logformatter = logging.Formatter('%(asctime)s -- %(levelname)s: (%(threadName)-10s) Module: %(module)s | Function: %(funcName)s | Message: %(message)s',
                                 datefmt='%Y-%m-%d %H:%M:%S%z')

filehandler = logging.handlers.RotatingFileHandler('iLoveDemocracy.log', maxBytes=10000000, backupCount=3)
filehandler.setFormatter(logformatter)
logger.addHandler(filehandler)

streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logformatter)
logger.addHandler(streamhandler)



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
            await self.tree.sync()
            self.synced = True
        logging.info(f'Bot has logged in as {self.user}')


client = Palpy()
polls = {}


# I hate this
@client.tree.command(name='newpoll', description='Set up a new poll')
async def newpoll(interaction, name: str, choice1: str, choice2: Optional[str] = None,
                  choice3: Optional[str] = None, choice4: Optional[str] = None, choice5: Optional[str] = None,
                  choice6: Optional[str] = None, choice7: Optional[str] = None, choice8: Optional[str] = None,
                  choice9: Optional[str] = None, time_limit: Optional[float] = 24., description: Optional[str] = None, 
                  poll_type: Optional[str] = 'STAR', winners: Optional[int] = 1):
    global polls
    c_all = [choice1, choice2, choice3, choice4, choice5, choice6, choice7, choice8, choice9]
    choices = []
    for c in c_all:
        if c is not None:
            choices.append(c)
    newpoll = Poll(interaction.user.id, interaction.channel, name, description, choices, n_winners=winners, type=poll_type, 
                   timeout=time_limit*3600)
    await interaction.response.send_message(embed=newpoll.embed, view=newpoll.view)
    message = await interaction.original_response()
    newpoll.message = message
    polls[name] = newpoll
    newpoll.message_update_loop.start()
    
@client.tree.command(name='getballot', description='Get a ballot for the poll')
async def getballot(interaction, name: str):

    # Get the poll we want a ballot for
    poll = polls[name]
    logging.info(f'{interaction.user.id} has requested a ballot for the poll "{name}"')

    # Keep track of the user who requested a ballot - only one per user!
    if interaction.user.id in poll.voters:
        await interaction.response.send_message("Sorry, you've already voted in this poll. Only one ballot per person!", ephemeral=True)
        return
    
    # check what type of poll we're dealing with
    if poll.type == 'STV':

        ballot_view = ui_elements.STVView(n=len(poll.choices), poll=poll, choices=poll.choices)

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
        return
    
    elif poll.type == 'STAR':

        container = ui_elements.STAR(n=len(poll.choices), poll=poll, choices=poll.choices)

        description = f"""
        **{poll.name}**

        Please rate your choices on a scale of 0-5 stars using the
        following buttons. A score of 5 stars is the best and 0 stars
        is the worst (to give a candidate 0 stars, simply don't press
        any buttons for them). You are allowed to give multiple
        candidates the same score, if you support them equally.

        When finished, please submit using the submit button.
        The poll results are tracked in real time on the embed
        shown during the poll's creation. After the time limit is up,
        the poll results will be announced in a separate message.\n
        """

        # description
        await interaction.response.send_message(description, ephemeral=True)
        # messages for each candidate
        choice_messages = []
        for i in range(container.n):
            msg = await interaction.followup.send(container.choices[i], view=container.choice_views[i], ephemeral=True, wait=True)
            choice_messages.append(msg)
        # submit message
        await interaction.followup.send(view=container.submit_view, ephemeral=True)
        # need to set these so the submit button can disable them later
        container.submit_view.choice_messages = choice_messages

        return


@client.tree.command(name='closepoll', description='Manually close a poll')
async def closepoll(interaction, name: str):

    poll = polls[name]
    if interaction.user.id != poll.creator:
        await interaction.response.send_message('Only the creator of the poll can close it!', ephemeral=True)
        return

    logging.info(f'Poll {name} has been manually closed. Printing results.')
    await interaction.response.send_message(f'{interaction.user.name} has closed the poll "{name}" early! The results will now be shown.')
    await poll.cleanup()


class Poll:

    def __init__(self, creator, channel, poll_name='Generic Poll', description=None, 
                 poll_choices=None, n_winners=1, type='STAR', timeout=24*3600):
        self.creator = creator                                      # the user ID of whoever made the poll
        self.channel = channel                                      # channel the poll is in
        self.name = poll_name                                       # name of the poll
        self.choices = poll_choices                                 # initialize the choices/candidates
        self.ballots = np.zeros((len(poll_choices),0), dtype=int)   # initialize an array for the ballots
        self.voters = np.zeros((0,), dtype=int)                     # store user IDs for each voter
        self.n_votes = 0
        self.n_winners = n_winners                                  # how many winners the poll will have (has no effect on STAR polls)
        self.timeout = timeout                                      # poll time limit in seconds
        self.time0 = time.monotonic()                               # starting time of the poll
        self.closed = False                                         # if the poll is closed
        self.embed = None                                           # will hold the embed
        self.view = None                                            # will hold the view 
        self.message = None                                         # will hold the message
        self.buttons = []                                           # will hold the buttons
        self.type = type

        notice = f'''\n
        To obtain your voting ballot for this poll, use the button at the bottom 
        of this message. The choices are listed below. This poll will have 
        {self.n_winners} winners.
        '''
        if description is None:
            if self.type == 'STV':
                description = f'''
                This is a ranked-choice (AKA alternative) voting poll! You will be able to rank
                each of the options in the poll from your 1st most preferred choice to your least
                preferred choice, and the end result will be calculated in a way that (hopefully)
                makes the most people happy as possible.''' 
            elif self.type == 'STAR':
                description = f'''
                This is a score voting poll! You will be able to rank each of the options in the
                poll by giving them 0-5 stars. More stars = more support, so give your favorites
                a 5 and give your least favorites a 0. At the end the results will be calculated
                in a way that (hopefully) makes the most people happy as possible.
                '''
        self.description = description + notice                              # description of the poll

        self.make_pretty_embed()
        self.make_button_view()
    
        logging.info(f'A new poll "{self.name}" has been created with the options {self.choices}')
    
    def make_pretty_embed(self):
        embed = discord.Embed(title=self.name, description=self.description, color=discord.Color.from_str('#663399'),
                              timestamp=datetime.datetime.now())   # rebeccapurple
        places = ''
        if self.type == 'STV':
            for i in range(len(self.choices)):
                places += f'**0**   *{ui_elements.get_place_str(i+1)}-choice votes*\n'
        elif self.type == 'STAR':
            for i in range(5,-1,-1):
                places += f'**0**   *{i} ⭐ votes*\n'
        for i, choice in enumerate(self.choices):
            embed.add_field(name=choice, value=places, inline=True)
        embed.set_footer(text=f'{self.n_votes} voter(s)\nThis poll closes in {ui_elements.time_formatter(self.timeout)}')
        self.embed = embed
    
    @tasks.loop(seconds=60)
    async def message_update_loop(self):
        assert self.message is not None                                     # make sure message is set
        self.message = await self.channel.fetch_message(self.message.id)    # fetch the message from its ID, otherwise expires after 15 mins
        time1 = time.monotonic()
        dt = time1 - self.time0
        time_remaining = self.timeout - dt
        if time_remaining > 0:
            logging.info('Updating poll embed')
            places = ['' for _ in range(len(self.choices))]
            if self.type == 'STV':
                for i in range(len(self.choices)):
                    for j in range(len(self.choices)):
                        current_votes = np.sum(self.ballots[j,:] == i+1)
                        places[j] += f'**{current_votes}**   *{ui_elements.get_place_str(i+1)}-choice votes*\n'
            elif self.type == 'STAR':
                for i in range(5,-1,-1):
                    for j in range(len(self.choices)):
                        current_votes = np.sum(self.ballots[j,:] == i)
                        places[j] += f'**{current_votes}**   *{i} ⭐ votes*\n'
            # update items
            for i, choice in enumerate(self.choices):
                self.embed.set_field_at(i, name=choice, value=places[i])
            # update footer
            self.embed = self.embed.set_footer(text=f'{self.n_votes} votes\nThis poll closes in {ui_elements.time_formatter(time_remaining)}')
            self.embed.timestamp = datetime.datetime.now()
            await self.message.edit(embed=self.embed)
        else:
            await self.channel.send(f'The poll "{self.name}" is now closed! The results will now be shown.')
            await self.cleanup()
    
    async def cleanup(self):
        # do a final update to the embed
        logging.info('Updating poll embed')
        self.message = await self.channel.fetch_message(self.message.id)
        places = ['' for _ in range(len(self.choices))]
        if self.type == 'STV':
            for i in range(len(self.choices)):
                for j in range(len(self.choices)):
                    current_votes = np.sum(self.ballots[j,:] == i+1)
                    places[j] += f'**{current_votes}**   *{ui_elements.get_place_str(i+1)}-choice votes*\n'
        elif self.type == 'STAR':
            for i in range(5,-1,-1):
                for j in range(len(self.choices)):
                    current_votes = np.sum(self.ballots[j,:] == i)
                    places[j] += f'**{current_votes}**   *{i} ⭐ votes*\n'
        # update items
        for i, choice in enumerate(self.choices):
            self.embed.set_field_at(i, name=choice, value=places[i])
        # update footer
        self.embed.set_footer(text=f'{self.n_votes} votes\nThis poll is now closed!')
        await self.message.edit(embed=self.embed)

        global polls

        # run the results
        logging.info(f'Poll {self.name} has closed. Printing results.')
        output = self.run_election()
        for i,oi in enumerate(output):
            await self.channel.send('```' + oi + '```', silent=False if i == 0 else True)
            await asyncio.sleep(0.5)

        self.closed = True
        await self.disable_buttons()

        polls.pop(self.name)
        self.message_update_loop.cancel()
        del self
    
    def make_button_view(self):
        self.view = discord.ui.View(timeout=self.timeout)
        ballot_btn = BallotButton(self.name)
        close_btn = CloseButton(self.name)
        self.buttons = [ballot_btn, close_btn]
        self.view.add_item(ballot_btn)
        self.view.add_item(close_btn)
    
    async def disable_buttons(self):
        for btn in self.buttons:
            btn.disabled = True
        await self.message.edit(view=self.view)

    def add_new_ballot(self, ballot, user_id):
        # check if the poll is still going
        time1 = time.monotonic()
        if time1 - self.time0 > self.timeout:
            self.closed = True
            return False
        if user_id in self.voters:
            return False
        logging.info(f'A user has cast their vote for the poll "{self.name}": {ballot}')
        ballot = ballot.reshape((len(ballot),1))
        self.ballots = np.concatenate((self.ballots, ballot), axis=1)
        self.voters = np.append(self.voters, user_id)
        self.n_votes += 1
        logging.debug(ballot)
        np.savez(f'{self.name}.ballot.npz', candidates=self.choices, ballots=self.ballots, voters=self.voters)
        return True
    
    def run_election(self, quiet=False):
        # get the results of the poll
        if type == 'STV':
            output = rcv.run_election(self.choices, self.ballots, self.n_winners)
            if not quiet:
                logging.info(''.join(output))
        else:
            # output = star.run_election(self.choices, self.ballots)
            output = star.run_election(self.choices, self.ballots, self.n_winners)
            if not quiet:
                logging.info(''.join(output))
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
