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

# ----------------- #
# User CFG Classes  #
# ----------------- #
class userConfig():
    def __init__(self, configdir='cfg/login.ini'):
        self.username = ''
        self.password = ''
        self.configdir = configdir
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

    def set_credentials(self, username, password):
        self.config['USER'] = {'username': username, 'password': password}
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.username = username
        self.password = password

    def clear_credentials(self):
        self.set_credentials('', '')

    def has_credentials(self):
        return bool(self.username.strip() and self.password.strip())

    def __str__(self):
        return f'User: {self.username}\nPassword: {self.password}'
    
# ----------------- #
# UI CFG Classes    #
# ----------------- #
class uiConfig():
    def __init__(self, configdir='cfg/ui.ini'):
        self.theme = 'dark'
        self.configdir = configdir
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
            self.theme = theme_name
            self.config['THEME']['theme'] = theme_name
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        # print(f'Set password for {self.username}')

    def __str__(self):
        return f'Theme: {self.theme}'
    
# ----------------- #
# Room CFG Classes  #
# ----------------- #

class roomsConfig():
    def __init__(self, configdir='cfg/recentrooms.ini', max_rooms=5):
        self.rooms = []
        self.max_rooms = self._clean_limit(max_rooms)
        self.configdir = configdir
        self.config = ConfigParser()

        if not os.path.exists(self.configdir):
            self.create_config()
        else:
            self.load_configs()

    def create_config(self):
        self.config['ROOMS'] = {
            'rooms': '',
            'max_rooms': str(self.max_rooms)
        }
        self._write()

    def load_configs(self):
        self.config.read(self.configdir)
        self.max_rooms = self._clean_limit(
            self.config.get('ROOMS', 'max_rooms', fallback=str(self.max_rooms))
        )
        # only load rooms, no pms or empty entries
        raw_rooms = self.config.get('ROOMS', 'rooms', fallback='').split(',')
        rooms_by_key = {}
        for room_name in raw_rooms:
            room_name = room_name.strip()
            if not room_name.startswith('#'):
                continue
            rooms_by_key.pop(room_name.casefold(), None)
            rooms_by_key[room_name.casefold()] = room_name
        # only keep the last max_rooms rooms
        self.rooms = list(rooms_by_key.values())[-self.max_rooms:]
        if not self.config.has_section('ROOMS'):
            self.config.add_section('ROOMS')
        self._write()

    def _write(self):
        self.config.set('ROOMS', 'rooms', ','.join(self.rooms))
        self.config.set('ROOMS', 'max_rooms', str(self.max_rooms))
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)

    def _clean_limit(self, limit):
        try:
            return max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            return 5

    def set_max_rooms(self, limit):
        self.max_rooms = self._clean_limit(limit)
        self.rooms = self.rooms[-self.max_rooms:]
        self._write()

    def clear_rooms(self):
        self.rooms = []
        self._write()

    def add_room(self, room_name):
        # don't add empty strings or pms
        if not isinstance(room_name, str):
            return
        room_name = room_name.strip()
        if not room_name.startswith('#'):
            return
        existing = next((room for room in self.rooms if room.casefold() == room_name.casefold()), None)
        if existing:
            # move to top of list
            self.rooms.remove(existing)
        self.rooms.append(room_name)
        # maximum list length
        self.rooms = self.rooms[-self.max_rooms:]
        self._write()

    def remove_room(self, room_name):
        if not isinstance(room_name, str):
            return
        existing = next((room for room in self.rooms if room.casefold() == room_name.casefold()), None)
        if not existing:
            return
        self.rooms.remove(existing)
        self._write()

    def __str__(self):
        return f'Rooms: {self.rooms}'
