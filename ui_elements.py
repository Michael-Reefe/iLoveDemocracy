import discord
import numpy as np
import logging

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

class PollSelectMenu(discord.ui.Select):
   
    # Make a select menu with knowledge of the view it's encased in
    def __init__(self, ni=0, choices=None):
        super().__init__(row=ni, min_values=1, max_values=1, 
                         placeholder=f'Choose your {get_place_str(ni+1)} option',
                         options=[])
        self.ni = ni                        # row index of the select menu 
        self.choices = choices              # the choices
        self.selected = False               # no selection has been made yet
        self.create_initial_options()
    
    def create_initial_options(self):
        if self.ni == 0:
            for i, choice in enumerate(self.choices):
                self.add_option(label=choice, value=str(i))

    async def callback(self, interaction):

        # remove any previously set defaults
        for i in range(len(self.options)):
            self.options[i].default = False
        # make the current selection the default so it remains
        opt_vals = np.array([opt.value for opt in self.options])
        self.options[np.where(opt_vals == self.values[0])[0][0]].default = True

        # after a selection has been made, enable the next drop-down menu with the remaining options
        if self.ni < min(len(self.choices)-1, 3):
            # if this menu or any future menus already exist, remove them
            for i in range(self.ni+1, len(self.view.select_menus)):
                if self.view.select_menus[i] != 0:
                    self.view.remove_item(self.view.select_menus[i])
                    self.view.select_menus[i] = 0
            next_menu = PollSelectMenu(ni=self.ni+1, choices=self.choices)
            prev_menu = self.view.select_menus[0:self.ni]
            prev_vals = [pm.values[0] for pm in prev_menu]
            prev_vals += self.values[0]
            for i, choice in enumerate(self.choices):
                if str(i) not in prev_vals:
                    next_menu.add_option(label=choice, value=str(i))
            self.view.select_menus[self.ni+1] = next_menu
            self.view.add_item(next_menu)
            # enable the submit button
            self.view.submit_btn.disabled = False

        # update the message view
        await interaction.response.edit_message(view=self.view) 


class SubmitButton(discord.ui.Button):

    def __init__(self):
        # start disabled
        super().__init__(style=discord.ButtonStyle.green, label=f'Submit', row=4, disabled=True)
    
    async def callback(self, interaction):
        # first: create the ballot
        ballot = self.view.get_ballot()
        # second: append the ballot to the poll object
        added_ballot = self.view.poll.add_new_ballot(ballot, interaction.user.id)
        # third: disable the submit button and all other menus
        self.disabled = True
        if type(self.view) is STVView:
            for i in range(len(self.view.select_menus)):
                if self.view.select_menus[i] != 0:
                    self.view.select_menus[i].disabled = True
        elif type(self.view) is STARSubmitView:
            for choice_view in self.view.choice_views:
                for btn in choice_view.buttons:
                    btn.disabled = True
        else:
            raise ValueError("wtf did you do")
        # fourth: edit the message confirming that the ballot has been submitted
        content = 'Thanks, your ballot has been submitted!' 
        embed = None
        if not added_ballot:
            if self.view.poll.closed:
                content = 'Sorry, the poll is now closed!'
            else:
                content = "You sneaky little wretch. You thought you could try to game the system by " + \
                "requesting mutliple ballots at the same time?  Well guess what, I thought of that, and " + \
                "now that you've been caught you're going to jail.  Yep, that's right, I'm calling the " + \
                "police. Right now.  Voter fraud is a serious crime you know. How long do you think they'll " + \
                "lock you up for?  Months?  Years?  Well, I guess we'll find out. That is, if Michael Stevens " + \
                "from vsauce doesn't get to you first... "
                embed = discord.Embed(url="https://www.youtube.com/watch?v=OB0wsQrMC3c&list=PL75wEN6hwvjhNcoPqBgDpwevaFw6LPhOJ&index=40",
                                      title="He's coming for you", description="Better watch your back...")

        await interaction.response.edit_message(content=content, view=self.view, embed=embed)

        # need to also update the previous messages if its a star poll
        if type(self.view) is STARSubmitView:
            for i in range(len(self.view.choice_messages)):
                msg = self.view.choice_messages[i]
                view = self.view.choice_views[i]
                # await msg.edit(view=view)

class STVView(discord.ui.View):

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
        select_menu = PollSelectMenu(ni=0, choices=self.choices)
        self.select_menus[0] = select_menu 
        self.add_item(select_menu)
        # Add the submit button
        self.submit_btn = SubmitButton()
        self.add_item(self.submit_btn)
    
    def get_ballot(self):
        # convert the select menu selections into a ballot
        ballot = np.zeros(self.n, dtype=int)
        for j in range(min(self.n, 4)):
            if self.select_menus[j] != 0:
                if len(self.select_menus[j].values) > 0:
                    ballot[int(self.select_menus[j].values[0])] = j + 1

        return ballot


class PollButton(discord.ui.Button):

    def __init__(self, nj):
        super().__init__(row=0, label=f'{nj+1} ⭐', style=discord.ButtonStyle.grey)
        self.nj = nj
        self.pressed = False
    
    async def callback(self, interaction):
        # if another button in the current view is pressed, unpress it
        for button in self.view.buttons:
            if button.pressed and button is not self:
                button.pressed = False
                button.style = discord.ButtonStyle.grey
        # press the current button
        if not self.pressed:
            self.style = discord.ButtonStyle.blurple
            self.pressed = True
        else:
            self.style = discord.ButtonStyle.grey
            self.pressed = False
        await interaction.response.edit_message(view=self.view)


class STARChoiceView(discord.ui.View):

    def __init__(self, n, poll, choices=None, timeout=3600, *args, **kwargs):
        super().__init__(timeout=timeout, *args, **kwargs)
        self.n = n
        self.poll = poll
        self.buttons = np.zeros(5, dtype=object)
        if choices is None:
            choices = []
        self.choices = choices
        self.create_view()

    def create_view(self):        
        # I hate everything about this
        for j in range(5):
            btn = PollButton(nj=j)
            self.buttons[j] = btn
            self.add_item(btn)

class STARSubmitView(discord.ui.View):

    def __init__(self, n, poll, choice_views=None, timeout=3600, *args, **kwargs):
        super().__init__(timeout=timeout, *args, **kwargs)
        self.n = n
        self.poll = poll
        self.choice_views = choice_views
        # will be filled in later:
        self.choice_messages = None
        assert len(self.choice_views) == self.n
        self.submit_btn = None
        self.create_view()
    
    def create_view(self):
        self.submit_btn = SubmitButton()
        # STAR voting is much more lenient in the accepted format - can submit right away (all 0s) or at any point later
        self.submit_btn.disabled = False
        self.add_item(self.submit_btn)
    
    def get_ballot(self):
        # check which button is pressed in each choice view
        ballot = np.zeros(self.n, dtype=int)
        for i, choice_view in enumerate(self.choice_views):
            for btn in choice_view.buttons:
                if btn.pressed:
                    assert ballot[i] == 0
                    ballot[i] = btn.nj + 1
        return ballot


class STAR:

    def __init__(self, n, poll, choices=None, timeout=3600):

        # set base attributes
        self.n = n
        self.poll = poll
        if choices is None:
            choices = []
        self.choices = choices

        # set a button view for each poll choice
        self.choice_views = []
        for choice in self.choices:
            btn_view = STARChoiceView(self.n, self.poll, self.choices, timeout=timeout)
            self.choice_views.append(btn_view)
        
        # set the final submit button view
        self.submit_view = STARSubmitView(self.n, self.poll, self.choice_views, timeout=timeout)
