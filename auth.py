from configparser import ConfigParser
import os

class configObj():
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