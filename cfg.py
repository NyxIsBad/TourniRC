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
            'theme': 'dark'}

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
            # TODO: implement
            self.create_config()
        else:
            # scan directory for config files
            self.load_config()
    
    def create_config(self):
        pass

    def load_config(self):
        # scan directory for .ini files
        for file in os.listdir(self.dir):
            if file.endswith('.ini'):
                # create a new tourneyConfig object and add it to the dict
                tourney = tourneyConfig()
                tourney.name = file.split('.')[0]
                self.tournaments[tourney.name] = tourney

    def get_tourney(self, name:str) -> "tourneyConfig":
        return self.tournaments[name]
        

class tourneyConfig():
    def __init__(self):
        self.name = ""
        self.configdir = f'cfg/tournaments/{self.name}.ini'