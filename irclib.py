import osu_irc
import logging

class Client(osu_irc.Client):
    def __init__(self, token: str, nickname: str, logger: logging.Logger):
        super().__init__(token=token, nickname=nickname)
        self.logger = logger
        self.msgs = {}

    async def onReady(self):
        # although we default to osu for debugging, we eventually want this to be Bancho Bot later.
        await self.joinChannel("#osu")
        self.logger.info(f"Connected to server")

    async def onMessage(self, message: osu_irc.Message):
        # TODO: add message to msgs list. It should be a dictionary with the key for channel and the value a list of messages & times
        print(f"Message from {message.user_name}: {message.content}")