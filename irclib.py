import osu_irc

class Client(osu_irc.Client):
    async def onReady(self):
        await self.joinChannel("#osu")
        print(f"Connected to server")

    async def onMessage(self, message: osu_irc.Message):
        print(f"Message from {message.user_name}: {message.content}")