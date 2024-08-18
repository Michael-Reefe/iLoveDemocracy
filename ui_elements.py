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

        if description is None:
            description = f'''
            This is a ranked-choice (AKA alternative) voting poll! You will be able to rank
            each of the options in the poll from your 1st most preferred choice to your least
            preferred choice, and the end result will be calculated in a way that makes the
            most people happy as possible. 

            To obtain your voting ballot for this poll, type the command `/getballot {self.name}`
            The choices are listed below.
            '''
        self.description = description                              # description of the poll
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
        return True
    
    def run_election(self, quiet=False):
        # get the results of the poll
        _, output = rcv.run_election(self.choices, self.ballots)
        if not quiet:
            print(output)
        return output


class PollButton(discord.ui.Button):

    # Make a button with knowledge of the view it's encased in
    def __init__(self, ni=0, nj=0, choice='', parent_view=None):
        label = (choice + '\n' if ni == 0 else '') + f'({ni+1})'
        super().__init__(style=discord.ButtonStyle.grey, label=label, row=nj)
        self._parent_view = parent_view     # stored reference of the parent
        self.ni = ni                        # column index of the button 
        self.nj = nj                        # row index of the button
        self.choice = choice                # a button may have a choice label on it
        self.pressed = False                # keeps track of the button state (pressed or not pressed)
        self.disable_level = 0              # anything > 0 will cause it to be disabled

    async def callback(self, interaction):
        if not self.pressed:
            # disable all other buttons with the same number and all other buttons in the same row
            # i indexes the column (which dictates the button number) and j indexes the row
            for i in range(self._parent_view.buttons.shape[0]):
                if i != self.ni:
                    self._parent_view.buttons[i,self.nj].disable_level += 1
                    self._parent_view.buttons[i,self.nj].label = f'({i+1})'
            for j in range(self._parent_view.buttons.shape[1]):
                if j != self.nj:
                    self._parent_view.buttons[self.ni,j].disable_level += 1
            # highlight the button that was selected
            self.style = discord.ButtonStyle.blurple
            # move the name of the choice onto this button
            self.label = self._parent_view.choices[self.nj] + '\n' + f'({self.ni+1})'
            # update the pressed state
            self.pressed = True
        else:
            # re-enable all other buttons 
            for i in range(self._parent_view.buttons.shape[0]):
                if i != self.ni:
                    self._parent_view.buttons[i,self.nj].disable_level -= 1
            for j in range(self._parent_view.buttons.shape[1]):
                if j != self.nj:
                    self._parent_view.buttons[self.ni,j].disable_level -= 1
            # un-highlight the button that was selected
            self.style = discord.ButtonStyle.grey
            # update the pressed state
            self.pressed = False
        # actually change the button states
        self._parent_view.change_button_states()
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
        # third: disable the submit button and all other buttons
        self.disabled = True
        for i in range(self._parent_view.n):
            for j in range(self._parent_view.n):
                self._parent_view.buttons[i,j].disabled = True
        # fourth: edit the message confirming that the ballot has been submitted
        content = 'Thanks, your ballot has been submitted!' if added_ballot else 'Sorry, the poll is now closed!'
        await interaction.response.edit_message(content=content, view=self._parent_view)

class BallotView(discord.ui.View):

    def __init__(self, n, poll, choices=None, timeout=3600, *args, **kwargs):        
        super().__init__(timeout=timeout, *args, **kwargs)          # Default timeout is 1 hour
        self.n = n                                                  # number of items in the poll
        self.poll = poll                                            # the actual poll object
        self.buttons = np.full((n,n), dtype=object, fill_value=0.)  # a 2D array that will hold the buttons
        self.submit_btn = None                                      # holds the submit button
        if choices is None:
            choices = []
        self.choices = choices
        self.create_view()
    
    def create_view(self):        
        # I hate everything about this
        for i in range(self.n):
            for j in range(self.n):
                button = PollButton(ni=i, nj=j, choice=self.choices[j], parent_view=self)
                self.buttons[i,j] = button
                self.add_item(button)
        # Add the submit button
        self.submit_btn = SubmitButton(parent_view=self)
        self.add_item(self.submit_btn)

    def change_button_states(self):
        # need to use disable levels because a button could be 'locked' by multiple other buttons
        for button in self.buttons.ravel():
            if button.disable_level > 0:
                button.disabled = True
            else:
                button.disabled = False
        # check if the submit button should be enabled
        numbers_pressed = np.zeros(self.n, dtype=bool)
        for i in range(self.n):
            for j in range(self.n):
                if self.buttons[i,j].pressed:
                    numbers_pressed[i] = True
        wh = np.where(numbers_pressed)[0]
        submit = numbers_pressed[0] and np.all(np.diff(wh) < 2)
        if submit:
            self.submit_btn.disabled = False
        else:
            self.submit_btn.disabled = True
    
    def get_ballot(self):
        # check which buttons are pressed and create the ballot
        ballot = np.zeros(self.n, dtype=int)
        for j in range(self.n):
            for i in range(self.n):
                if self.buttons[i,j].pressed:
                    ballot[j] = i+1

        return ballot
