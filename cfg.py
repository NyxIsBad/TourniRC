from configparser import ConfigParser
import os
from typing import *

THEMES = [
    "light", "dark", "cupcake", "bumblebee", "emerald",
    "corporate", "synthwave", "retro", "cyberpunk", "valentine",
    "halloween", "garden", "forest", "aqua", "lofi",
    "pastel", "fantasy", "wireframe", "black", "luxury",
    "dracula", "cmyk", "autumn", "business", "acid",
    "lemonade", "night", "coffee", "winter", "dim",
    "nord", "sunset"
]

class userConfig():
    def __init__(self):
        self.username = ''
        self.password = ''
        self.configdir = f'cfg/login.ini'
        self.config = ConfigParser()

        if not os.path.exists(self.configdir):
            self.create_config()
        else:
            self.load_config()
    
    def create_config(self):
        self.config['USER'] = {
            'username': '', # empty by default
            'password': '' # empty by default, obviously
        }

        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.password = ''
        # print(f'Created config for {self.username}')

    def load_config(self):
        self.config.read(self.configdir)
        self.username = self.config['USER']['username']
        self.password = self.config['USER']['password']
        # print(f'Loaded config for {self.username}')

    def get_username(self):
        return self.username
    
    def get_password(self):
        return self.password

    def set_password(self, password):
        self.config['USER']['password'] = password
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.password = password
        # print(f'Set password for {self.username}')

    def set_username(self, username):
        self.config['USER']['username'] = username
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.username = username
        # print(f'Set username for {self.username}')

    def __str__(self):
        return f'User: {self.username}\nPassword: {self.password}'
    
class uiConfig():
    def __init__(self):
        self.theme = 'dark'
        self.configdir = f'cfg/ui.ini'
        self.config = ConfigParser()

        if not os.path.exists(self.configdir):
            self.create_config()
        else:
            self.load_config()
    
    def create_config(self):
        self.config['THEME'] = {
            'theme': 'dark'
        }

        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        # print(f'Created config for {self.username}')

    def load_config(self):
        self.config.read(self.configdir)
        self.theme = self.config['THEME']['theme']

    def get_theme(self):
        self.load_config()
        return self.theme

    def set_theme(self, theme_name):
        if theme_name in THEMES:
            self.config['THEME']['theme'] = theme_name
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        # print(f'Set password for {self.username}')

    def __str__(self):
        return f'Theme: {self.theme}'
    
# we can have tourney config files here later

class Tournaments():
    def __init__(self):
        self.tournaments:Dict[str, tourneyConfig] = {}
        self.dir = f'cfg/tournaments/'
        self.config = ConfigParser()

        if not os.path.exists(self.dir):
            os.makedirs(self.dir)
        else:
            self.load_configs()
    
    def create_tournament(self, name:str):
        self.tournaments[name] = tourneyConfig()

    def load_configs(self):
        # scan directory for .ini files
        for file in os.listdir(self.dir):
            if file.endswith('.ini'):
                # create a new tourneyConfig object and add it to the dict
                tourney = tourneyConfig()
                tourney.name = file.split('.')[0]
                self.tournaments[tourney.name] = tourney

    def get_tourney(self, name:str):
        return self.tournaments[name]
    
    def get_all_tourneys(self):
        return self.tournaments
    
    def __str__(self):
        return f'Tournaments: {self.tournaments}'

class tourneyConfig():
    def __init__(self):
        self.name = ""
        self.configdir = f'cfg/tournaments/{self.name}.ini'

        self.acronym = ""
        self.maps:Dict[str, str] = {}
        self.timer = 120
        self.match_timer = 5

        self.config = ConfigParser()

        if not os.path.exists(self.configdir):
            self.create_config()
        else:
            self.load_config()

    def create_config(self):
        self.config['TOURNAMENT'] = {
            'acronym': '', # Acronym of tournament that will appear in the title TODO: make the UI autodetect for these
            'timer': '120', # Default to 120
            'match_timer': '5' # Default to 50
        }
        self.config['MAPS'] = {

        }

        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
    
    def load_config(self):
        self.config.read(self.configdir)
        self.acronym = self.config['TOURNAMENT']['acronym']
        self.timer = int(self.config['TOURNAMENT']['timer'])
        self.match_timer = int(self.config['TOURNAMENT']['match_timer'])
        self.maps = dict(self.config['MAPS'])

    def set_acronym(self, acronym:str):
        self.config['TOURNAMENT']['acronym'] = acronym
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.acronym = acronym

    def set_timer(self, timer:int):
        self.config['TOURNAMENT']['timer'] = str(timer)
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.timer = timer

    def set_match_timer(self, timer:int):
        self.config['TOURNAMENT']['match_timer'] = str(timer)
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.match_timer = timer

    def add_map(self, mapname:str, mapfile:str):
        self.config['MAPS'][mapname] = mapfile
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.maps[mapname] = mapfile

    def get_acronym(self):
        return self.acronym
    
    def get_timer(self):
        return self.timer
    
    def get_match_timer(self):
        return self.match_timer
    
    def get_maps(self):
        return self.maps
    
    def __str__(self):
        return f'Tournament: {self.acronym} Timer: {self.timer} Match Timer: {self.match_timer} Maps: {self.maps}'