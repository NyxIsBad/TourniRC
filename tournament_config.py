from configparser import ConfigParser
import os
from typing import Dict


# TODO: replace this with the preset database
# legacy only. core chat should never depend on this surviving.
class Tournaments():
    def __init__(self):
        self.tournaments: Dict[str, tourneyConfig] = {}
        self.dir = 'cfg/tournaments/'
        self.config = ConfigParser()

        if not os.path.exists(self.dir):
            os.makedirs(self.dir)
        else:
            self.load_configs()

    def create_tournament(self, name: str):
        self.tournaments[name] = tourneyConfig()

    def load_configs(self):
        # scan directory for .ini files
        for file in os.listdir(self.dir):
            if file.endswith('.ini'):
                # create a tournament from each file
                tourney = tourneyConfig()
                tourney.name = file.split('.')[0]
                self.tournaments[tourney.name] = tourney

    def get_tourney(self, name: str):
        return self.tournaments[name]

    def get_all_tourneys(self):
        return self.tournaments

    def __str__(self):
        return f'Tournaments: {self.tournaments}'


class tourneyConfig():
    def __init__(self):
        self.name = ''
        self.configdir = f'cfg/tournaments/{self.name}.ini'

        self.acronym = ''
        self.maps: Dict[str, str] = {}
        self.timer = 120
        self.match_timer = 5

        self.config = ConfigParser()

        if not os.path.exists(self.configdir):
            self.create_config()
        else:
            self.load_config()

    def create_config(self):
        self.config['TOURNAMENT'] = {
            'acronym': '', # TODO: autodetect this
            'timer': '120', # default to 120
            'match_timer': '5' # default to 5
        }
        self.config['MAPS'] = {}

        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)

    def load_config(self):
        self.config.read(self.configdir)
        self.acronym = self.config['TOURNAMENT']['acronym']
        self.timer = int(self.config['TOURNAMENT']['timer'])
        self.match_timer = int(self.config['TOURNAMENT']['match_timer'])
        self.maps = dict(self.config['MAPS'])

    def set_acronym(self, acronym: str):
        self.config['TOURNAMENT']['acronym'] = acronym
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.acronym = acronym

    def set_timer(self, timer: int):
        self.config['TOURNAMENT']['timer'] = str(timer)
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.timer = timer

    def set_match_timer(self, timer: int):
        self.config['TOURNAMENT']['match_timer'] = str(timer)
        with open(self.configdir, 'w') as configfile:
            self.config.write(configfile)
        self.match_timer = timer

    def add_map(self, mapname: str, mapfile: str):
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
