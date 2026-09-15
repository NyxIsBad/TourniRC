from configparser import ConfigParser, Error as ConfigParserError
import os
from pathlib import Path
import shutil
import socket
import time
from typing import *

WEB_HOST = os.environ.get('TOURNIRC_WEB_HOST', '127.0.0.1')


def _web_port() -> int:
    try:
        port = int(os.environ.get('TOURNIRC_WEB_PORT', '54247'))
    except ValueError:
        return 54247
    return port if 1 <= port <= 65535 else 54247


WEB_PORT = _web_port()


def find_web_port() -> int:
    """find a usable local port"""
    for port in range(WEB_PORT, min(WEB_PORT + 100, 65536)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind((WEB_HOST, port))
        except OSError:
            continue
        return port
    raise OSError(f'No available web port in range {WEB_PORT}-{WEB_PORT + 99}.')

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
        self.config = ConfigParser(interpolation=None)
        os.makedirs(os.path.dirname(self.configdir) or '.', exist_ok=True)

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
        try:
            with open(self.configdir, encoding='utf-8') as configfile:
                self.config.read_file(configfile)
            if not self.config.has_section('USER'):
                raise ValueError('Missing USER section.')
            self.username = self.config.get('USER', 'username')
            self.password = self.config.get('USER', 'password')
        except (OSError, ConfigParserError, ValueError):
            original = Path(self.configdir)
            backup = original.with_name(
                f'{original.stem}.invalid-{int(time.time())}{original.suffix}'
            )
            try:
                shutil.copy2(original, backup)
            except OSError:
                pass
            self.config = ConfigParser(interpolation=None)
            self.create_config()
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
# Room CFG Classes  #
# ----------------- #

class roomsConfig():
    def __init__(self, configdir='cfg/recentrooms.ini', max_rooms=5):
        self.rooms = []
        self.max_rooms = self._clean_limit(max_rooms)
        self.configdir = configdir
        os.makedirs(os.path.dirname(self.configdir) or '.', exist_ok=True)
        self.config = ConfigParser()

        if not os.path.exists(self.configdir):
            self.create_config()
        else:
            self.load_configs()

    def create_config(self):
        self.config['ROOMS'] = {
            'rooms': ''
        }
        self._write()

    def load_configs(self):
        self.config.read(self.configdir)
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
        self.config.remove_option('ROOMS', 'max_rooms')
        self.config.set('ROOMS', 'rooms', ','.join(self.rooms))
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
