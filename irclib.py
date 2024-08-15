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

        self.sio.on('bounce_send_msg', self.onBounceSendMessage)
        self.sio.on('bounce_tab_close', self.onBounceChatRemoved)
        self.sio.connect('http://127.0.0.1:5000')

    async def onReady(self):
        # although we default to osu for debugging, we eventually want this to be Bancho Bot later.
        await self.joinChannel("#osu")
        self.sio.emit('tab_open', {'name': "#osu", "type": osu_irc.CHANNEL_TYPE_ROOM})

    async def onMessage(self, message: osu_irc.Message):
        self.sio.emit('recv_msg', message.compact())
        print(f"Message from {message.user_name}: {message.content}")
    
    def onBounceSendMessage(self, data: Dict[str, Any]):
        print(f"Message bounced: {data}")

    def onBounceChatRemoved(self, data: Dict[str, Any]):
        print(f"Chat removed: {data}")
        # TODO: Leave channel with partChannel