import discord
from discord.ext import tasks
import numpy as np
import time
import datetime
import rcv

def time_formatter(seconds):
    if seconds > 3600*2:
        return f'{np.ceil(seconds/3600):.0f} hour(s)'
    else:
        return f'{np.ceil(seconds/60):.0f} minute(s)'

def get_place_str(number):
    s = str(number)
    if s[-1] == '1':
        if not (len(s) > 1 and s[-2] == '1'):
            return s + 'st'
    elif s[-1] == '2':
        if not (len(s) > 1 and s[-2] == '2'):
            return s + 'nd'
    elif s[-1] == '3':
        if not (len(s) > 1 and s[-2] == '3'):
            return s + 'rd'
    else:
        return s + 'th'

class Poll:

    def __init__(self, channel, poll_name='Generic Poll', description=None, 
                 poll_choices=None, timeout=24*3600):
        self.channel = channel                                      # channel the poll is in
        self.name = poll_name                                       # name of the poll
        self.choices = poll_choices                                 # initialize the choices/candidates
        self.ballots = np.zeros((len(poll_choices),0), dtype=int)   # initialize an array for the ballots
        self.voters = np.zeros((0,), dtype=int)                     # store user IDs for each voter
        self.n_votes = 0
        self.timeout = timeout                                      # poll time limit in seconds
        self.time0 = time.monotonic()                               # starting time of the poll
        self.closed = False                                         # if the poll is closed
        self.embed = None

        notice = f'''\n
        To obtain your voting ballot for this poll, type the command `/getballot {self.name}`
        The choices are listed below.
        '''
        if description is None:
            description = f'''
            This is a ranked-choice (AKA alternative) voting poll! You will be able to rank
            each of the options in the poll from your 1st most preferred choice to your least
            preferred choice, and the end result will be calculated in a way that makes the
            most people happy as possible.''' 
        self.description = description + notice                              # description of the poll
        self.make_pretty_embed()
    
    def make_pretty_embed(self):
        embed = discord.Embed(title=self.name, description=self.description, color=discord.Color.from_str('#663399'),
                              timestamp=datetime.datetime.now())   # rebeccapurple
        places = ''
        for i in range(len(self.choices)):
            places += f'**0**   *{get_place_str(i+1)}-choice votes*\n'
        for i, choice in enumerate(self.choices):
            embed.add_field(name=choice, value=places, inline=True)
        embed.set_footer(text=f'{self.n_votes} voter(s)\nThis poll expires in {time_formatter(self.timeout)}')
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
                places[j] += f'**{current_votes}**   *{get_place_str(i+1)}-choice votes*\n'
        # update items
        for i, choice in enumerate(self.choices):
            self.embed.set_field_at(i, name=choice, value=places[i])
        # update footer
        self.embed = self.embed.set_footer(text=f'{self.n_votes} votes\nThis poll expires in {time_formatter(time_remaining)}')
        await message.edit(embed=self.embed)

    def add_new_ballot(self, ballot, user_id):
        # check if the poll is still going
        time1 = time.monotonic()
        if time1 - self.time0 > self.timeout:
            self.closed = True
            return False
        ballot = ballot.reshape((len(ballot),1))
        self.ballots = np.concatenate((self.ballots, ballot), axis=1)
        self.voters = np.append(self.voters, user_id)
        self.n_votes += 1
        print(ballot)
        return True
    
    def run_election(self, quiet=False):
        # get the results of the poll
        _, output = rcv.run_election(self.choices, self.ballots)
        if not quiet:
            print(output)
        return output

class PollSelectMenu(discord.ui.Select):
   
    # Make a select menu with knowledge of the view it's encased in
    def __init__(self, ni=0, parent_view=None):
        super().__init__(row=ni, min_values=1, max_values=1, 
                         placeholder=f'Choose your {get_place_str(ni+1)} option',
                         options=[])
        self._parent_view = parent_view     # stored reference of the parent
        self.ni = ni                        # row index of the select menu 
        self.selected = False               # no selection has been made yet
        self.create_initial_options()
    
    def create_initial_options(self):
        if self.ni == 0:
            for i, choice in enumerate(self._parent_view.choices):
                self.add_option(label=choice, value=str(i))

    async def callback(self, interaction):

        # remove any previously set defaults
        for i in range(len(self.options)):
            self.options[i].default = False
        # make the current selection the default so it remains
        opt_vals = np.array([opt.value for opt in self.options])
        self.options[np.where(opt_vals == self.values[0])[0][0]].default = True

        # after a selection has been made, enable the next drop-down menu with the remaining options
        if self.ni < 3:
            # if this menu or any future menus already exist, remove them
            for i in range(self.ni+1, len(self._parent_view.select_menus)):
                if self._parent_view.select_menus[i] != 0:
                    self._parent_view.remove_item(self._parent_view.select_menus[i])
                    self._parent_view.select_menus[i] = 0
            next_menu = PollSelectMenu(ni=self.ni+1, parent_view=self._parent_view)
            prev_menu = self._parent_view.select_menus[0:self.ni]
            prev_vals = [pm.values[0] for pm in prev_menu]
            prev_vals += self.values[0]
            for i, choice in enumerate(self._parent_view.choices):
                if str(i) not in prev_vals:
                    next_menu.add_option(label=choice, value=str(i))
            self._parent_view.select_menus[self.ni+1] = next_menu
            self._parent_view.add_item(next_menu)
            # enable the submit button
            self._parent_view.submit_btn.disabled = False

        # update the message view
        await interaction.response.edit_message(view=self._parent_view) 

class SubmitButton(discord.ui.Button):

    def __init__(self, parent_view=None):
        # start disabled
        super().__init__(style=discord.ButtonStyle.green, label=f'Submit', row=4, disabled=True)
        self._parent_view = parent_view     # stored reference of the parent 
    
    async def callback(self, interaction):
        # first: create the ballot
        ballot = self._parent_view.get_ballot()
        # second: append the ballot to the poll object
        added_ballot = self._parent_view.poll.add_new_ballot(ballot, interaction.user.id)
        # third: disable the submit button and all other menus
        self.disabled = True
        for i in range(len(self._parent_view.select_menus)):
            if self._parent_view.select_menus[i] != 0:
                self._parent_view.select_menus[i].disabled = True
        # fourth: edit the message confirming that the ballot has been submitted
        content = 'Thanks, your ballot has been submitted!' if added_ballot else 'Sorry, the poll is now closed!'
        await interaction.response.edit_message(content=content, view=self._parent_view)

class BallotView(discord.ui.View):

    def __init__(self, n, poll, choices=None, timeout=3600, *args, **kwargs):        
        super().__init__(timeout=timeout, *args, **kwargs)          # Default timeout is 1 hour
        self.n = n                                                  # number of items in the poll
        self.poll = poll                                            # the actual poll object
        self.select_menus = np.zeros(min(n, 4), dtype=object)       # holds the select menus for each place
        self.submit_btn = None                                      # holds the submit button
        if choices is None:
            choices = []
        self.choices = choices
        self.create_view()
    
    def create_view(self):        
        # I hate everything about this
        select_menu = PollSelectMenu(ni=0, parent_view=self)
        self.select_menus[0] = select_menu 
        self.add_item(select_menu)
        # Add the submit button
        self.submit_btn = SubmitButton(parent_view=self)
        self.add_item(self.submit_btn)
    
    def get_ballot(self):
        # convert the select menu selections into a ballot
        ballot = np.zeros(self.n, dtype=int)
        for j in range(min(self.n, 4)):
            if self.select_menus[j] != 0:
                if len(self.select_menus[j].values) > 0:
                    ballot[int(self.select_menus[j].values[0])] = j + 1

        return ballot
