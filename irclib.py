import osu_irc
import logging
from socketio import Client as sioClient
from typing import *
import ui

class Client(osu_irc.Client):
    def __init__(self, token: str, nickname: str, logger: logging.Logger):
        super().__init__(token=token, nickname=nickname)
        self.logger = logger
        self.msgs = {}
        self.chats = {}
        self.sio = sioClient()
        self.sio.connect('http://127.0.0.1:5000')

    async def onReady(self):
        # although we default to osu for debugging, we eventually want this to be Bancho Bot later.
        await self.joinChannel("#osu")
        self.logger.info(f"Connected to server")

    async def onMessage(self, message: osu_irc.Message):
        if message.room_name not in self.chats:
            self.chats[message.room_name] = Chat(message.room_name, message.channel_type)
        self.chats[message.room_name].add_message(message)
        self.sio.emit('irc_msg', message.compact())
        print(f"Message from {message.user_name}: {message.content}")

class Chat():
    def __init__(self, channel_name: str, channel_type: int):
        self.type = channel_type
        self.channel_name = channel_name
        self.messages: List[osu_irc.Message] = []
        self.timer = 120 # default to 2 minutes
        self.start_timer = 5 # default to 5 seconds
        
    def add_message(self, message: osu_irc.Message) -> None:
        if message.room_name == self.channel_name:
            self.messages.append(message)
        else:
            raise ValueError(f"Message not in channel {self.channel_name}")
        
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} channel_name='{self.channel_name}' num_messages={len(self.messages)}>"

    def __str__(self) -> str:
        return f"Chat on channel {self.channel_name} with {len(self.messages)} messages."

    @property 
    def message_count(self) -> int:
        return len(self.messages)
    
    @property
    def get_messages(self) -> List[osu_irc.Message]:
        return self.messages
    
    def clear_messages(self):
        self.messages.clear()