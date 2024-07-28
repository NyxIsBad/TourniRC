from twisted.words.protocols import irc
from twisted.internet import protocol, reactor
from twisted.python import log

import time, sys

class Client(irc.IRCClient):
    def __init__(self, username, password):
        self.username = username
        self.password = password
    
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        print(f'Connected to server')

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)
        print(f"Disconnected from the server for {reason}")

    def signedOn(self):
        print(f"Signed in as {self.username}")

    def joined(self, channel):
        print(f"Joined {channel}")
    
    def irc_NOTICE(self, prefix, params):
        print(f"NOTICE from {prefix}: {params}")

    def irc_ERR_NICKNAMEINUSE(self, prefix, params):
        print("Nickname is already in use.")
        self.nickname = self.nickname + "_"
        self.register(self.nickname)

    def irc_RPL_WELCOME(self, prefix, params):
        print("Welcome message received from server.")
        self.msg("NickServ", f"IDENTIFY {self.username} {self.password}")

class ClientFactory(protocol.ClientFactory):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def buildProtocol(self, addr):
        return Client(self.username, self.password)

    def clientConnectionLost(self, connector, reason):
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print(f"Connection failed: {reason}")
        reactor.stop()