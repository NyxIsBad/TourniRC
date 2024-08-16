import osu_irc
import logging
from socketio import Client as sioClient
from typing import *
import ui


class Client(osu_irc.Client):
    def __init__(self, token: str, nickname: str, logger: logging.Logger):
        super().__init__(token=token, nickname=nickname)
        self.logger = logger
        self.nickname = nickname
        self.msgs = {}
        self.chats = {}
        self.sio = sioClient()
        print(f"{self.nickname} attempting to connect to server...")
        self.sio.connect('http://localhost:5000')
        self.sio.emit('nickname', {'nickname': nickname})

        self.sio.on('bounce_send_msg', self.onBounceSendMessage)
        self.sio.on('bounce_tab_close', self.onBounceChatRemoved)

    async def onReady(self):
        # although we default to osu for debugging, we eventually want this to be Bancho Bot later.
        await self.joinChannel("BanchoBot")
        self.sio.emit('tab_open', {'channel': "BanchoBot", "type": osu_irc.CHANNEL_TYPE_PM})

    # An exceedingly dumb way to get the correct case for the nickname
    # Works because osu echoes us joining any room/channel
    # Alternative methods probably would require an api
    async def onMemberJoin(self, channel: osu_irc.Channel, user: osu_irc.User):
        print(f"Member joined {channel}: {user}")
        if user.name.lower() == self.nickname:
            self.sio.emit('nickname', {'nickname': user.name})

    async def onMessage(self, message: osu_irc.Message):
        self.sio.emit('recv_msg', message.compact())
        print(f"Message from {message.user_name}: {message.content}")
    
    def onBounceSendMessage(self, data: Dict[str, Any]):
        print(f"Sending message: {data}")
        if data['type'] == osu_irc.CHANNEL_TYPE_PM:
            self.Loop.create_task(self.sendPM(data["channel"], data["content"]))
        elif data['type'] == osu_irc.CHANNEL_TYPE_ROOM:
            self.Loop.create_task(self.sendMessage(data["channel"], data["content"]))

    def onBounceChatRemoved(self, data: Dict[str, Any]):
        print(f"Chat removed: {data}")
        # TODO: Leave channel with partChannel