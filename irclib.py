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
        self.sio.on('cmd_req_ch', self.onRequestChannel)

    async def onReady(self):
        # although we default to osu for debugging, we eventually want this to be Bancho Bot later.
        await self.joinChannel("BanchoBot")
        self.sio.emit('tab_open', {'channel': "BanchoBot", "type": osu_irc.CHANNEL_TYPE_PM})

    async def onMemberJoin(self, channel: osu_irc.Channel, user: osu_irc.User):
        print(f"Member joined {channel}: {user}")
        if user.name.lower() == self.nickname:
            self.sio.emit('nickname', {'nickname': user.name})

    async def onMessage(self, message: osu_irc.Message):
        self.sio.emit('recv_msg', message.compact())
        print(f"Message from {message.user_name}: {message.content}")
    
    def onBounceSendMessage(self, data: Dict[str, Any]):
        print(data)
        if data['type'] == osu_irc.CHANNEL_TYPE_PM:
            self.Loop.create_task(self.sendPM(data["channel"], data["content"]))
        elif data['type'] == osu_irc.CHANNEL_TYPE_ROOM:
            self.Loop.create_task(self.sendMessage(data["channel"], data["content"]))

    def onBounceChatRemoved(self, data: Dict[str, Any]):
        print(f"Chat removed: {data}")
        self.Loop.create_task(self.partChannel(data["channel"]))

    def onRequestChannel(self, data: Dict[str, Any]):
        print(f"Requesting channel: {data}")
        task = self.Loop.create_task(self.joinChannel(data["channel"]))
        # When the task is done, we want to emit a tab_open event to the client
        task.add_done_callback(lambda x: self.sio.emit('tab_open', {'channel': data["channel"], "type": data["type"]}))