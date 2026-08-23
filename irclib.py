import asyncio
import logging
import threading
import time
from typing import Any, Dict, Optional

import osu_irc
from cfg import WEB_PORT
from socketio import Client as sioClient
from eventlog import EventLog


IRC_STATE_CONNECTING = "connecting"
IRC_STATE_AUTHENTICATED = "authenticated"
IRC_STATE_RECONNECTING = "reconnecting"
IRC_STATE_AUTH_FAILED = "authentication_failed"
IRC_STATE_LOGGED_OUT = "logged_out"
IRC_EVENTS = EventLog('irc', 'logs/irc-events.log')


class Client(osu_irc.Client):
    def __init__(self, token: str, nickname: str, logger: logging.Logger, sio: sioClient, **kwargs):
        super().__init__(token=token, nickname=nickname, **kwargs)
        self.logger = logger
        self.sio = sio
        self.restoring = False

    def emit_state(self, state: str, **details: Any) -> None:
        IRC_EVENTS.write('connection_state', state=state, **details)
        self.sio.emit('irc_state', {'state': state, **details})

    async def onConnecting(self, attempt: int):
        state = IRC_STATE_CONNECTING if not self.ever_authenticated else IRC_STATE_RECONNECTING
        self.emit_state(state, attempt=attempt, retry_in=0)

    async def onDisconnected(self, error: BaseException, attempt: int, retry_delay: float):
        reason = "The connection to Bancho was lost."
        if isinstance(error, osu_irc.Errors.PingTimeout):
            reason = "Bancho stopped responding to keepalive messages."
        self.emit_state(
            IRC_STATE_RECONNECTING,
            attempt=attempt,
            retry_in=round(retry_delay, 1),
            reason=reason
        )

    async def onAuthenticationFailed(self, error: BaseException):
        self.emit_state(
            IRC_STATE_AUTH_FAILED,
            attempt=0,
            retry_in=0,
            reason="The osu! username or IRC password was rejected."
        )

    async def onReady(self):
        self.sio.emit('nickname', {'nickname': self.nickname})
        state = self.sio.call('session_state', timeout=5) or {}
        chats = state.get('chats', [])

        if not chats:
            # open banchobot by default if nothing was open
            self.sio.emit('tab_open', {
                'channel': "BanchoBot",
                'type': osu_irc.CHANNEL_TYPE_PM
            })
        else:
            # reconnect and restore loop
            self.restoring = True
            for chat in chats:
                if chat.get('type') == osu_irc.CHANNEL_TYPE_ROOM:
                    await self.joinChannel(chat['channel'])
            self.restoring = False

        self.emit_state(IRC_STATE_AUTHENTICATED, attempt=0, retry_in=0)
        if state.get('current_chat'):
            self.sio.emit('restore_tab', {'channel': state['current_chat']})
    # reconnect logic and a lot of logs
    async def onReconnect(self):
        self.logger.info("Reauthenticated after a connection loss")
        IRC_EVENTS.write('reconnected')

    async def onRaw(self, raw: bytes):
        # ignore global quits here; tracked quits get parsed logs
        if b' QUIT :' in raw:
            return
        IRC_EVENTS.write('irc_received', raw=raw)

    async def onSend(self, raw: bytes):
        IRC_EVENTS.write('irc_sent', raw=raw)

    async def onUnknown(self, raw: str):
        IRC_EVENTS.write('irc_unknown', raw=raw)

    async def onGarbage(self, raw: str):
        IRC_EVENTS.write('irc_ignored', raw=raw)

    async def onError(self, error: BaseException):
        await super().onError(error)
        IRC_EVENTS.write('irc_error', error=error)

    async def onMemberJoin(self, channel: osu_irc.Channel, user: osu_irc.User):
        IRC_EVENTS.write('member_joined', channel=channel.name, username=user.name)
        if user.name.lower() == self.nickname.lower():
            self.sio.emit('nickname', {'nickname': user.name})

    async def onMemberPart(self, channel: osu_irc.Channel, user: osu_irc.User):
        IRC_EVENTS.write('member_parted', channel=channel.name, username=user.name)

    async def onMemberQuit(self, user: osu_irc.User, reason: str):
        IRC_EVENTS.write('member_quit', username=user.name, reason=reason)

    async def onMessage(self, message: osu_irc.Message):
        IRC_EVENTS.write('message_received', message=message.compact())
        self.sio.emit('recv_msg', message.compact())

    def send_from_ui(self, data: Dict[str, Any]):
        IRC_EVENTS.write('socket_command', name='bounce_send_msg', data=data)
        if not isinstance(data, dict) or not isinstance(data.get('content'), str):
            IRC_EVENTS.write('invalid_socket_command', name='bounce_send_msg', data=data)
            return
        if not isinstance(data.get('channel'), str) or data.get('type') not in {
            osu_irc.CHANNEL_TYPE_PM, osu_irc.CHANNEL_TYPE_ROOM
        }:
            IRC_EVENTS.write('invalid_socket_command', name='bounce_send_msg', data=data)
            return
        if not self.auth_success or not self.running:
            self.emit_state(
                IRC_STATE_RECONNECTING,
                attempt=self.reconnect_attempt,
                retry_in=0,
                reason="Messages cannot be sent while disconnected."
            )
            return
        if data['type'] == osu_irc.CHANNEL_TYPE_PM:
            self.Loop.call_soon_threadsafe(
                lambda: self.Loop.create_task(self.sendPM(data["channel"], data["content"]))
            )
        elif data['type'] == osu_irc.CHANNEL_TYPE_ROOM:
            self.Loop.call_soon_threadsafe(
                lambda: self.Loop.create_task(self.sendMessage(data["channel"], data["content"]))
            )

    def remove_chat(self, data: Dict[str, Any]):
        IRC_EVENTS.write('socket_command', name='bounce_tab_close', data=data)
        if not isinstance(data, dict):
            IRC_EVENTS.write('invalid_socket_command', name='bounce_tab_close', data=data)
            return
        if (
            data.get('type') != osu_irc.CHANNEL_TYPE_ROOM
            or not isinstance(data.get('channel'), str)
            or not self.auth_success
        ):
            return
        self.Loop.call_soon_threadsafe(
            lambda: self.Loop.create_task(self.partChannel(data["channel"]))
        )

    def request_channel(self, data: Dict[str, Any]):
        IRC_EVENTS.write('socket_command', name='cmd_req_ch', data=data)
        if not isinstance(data, dict):
            IRC_EVENTS.write('invalid_socket_command', name='cmd_req_ch', data=data)
            return
        if not isinstance(data.get('channel'), str) or data.get('type') not in {
            osu_irc.CHANNEL_TYPE_PM, osu_irc.CHANNEL_TYPE_ROOM
        }:
            IRC_EVENTS.write('invalid_socket_command', name='cmd_req_ch', data=data)
            return
        if not self.auth_success:
            return
        if data['type'] == osu_irc.CHANNEL_TYPE_PM:
            self.sio.emit('tab_open', data)
            return

        async def join_and_open():
            await self.joinChannel(data["channel"])
            self.sio.emit('tab_open', data)

        self.Loop.call_soon_threadsafe(lambda: self.Loop.create_task(join_and_open()))


class IrcSessionSupervisor:
    """
    owns all login sessions while keeping one local Socket.IO bridge alive
    this is what enables the stronger version of what brigitta had 
    """

    def __init__(self, logger: logging.Logger, server_url: str = f'http://localhost:{WEB_PORT}'):
        self.logger = logger
        self.server_url = server_url
        self.sio = sioClient(reconnection=True)
        self.active_client: Optional[Client] = None
        self._credentials: Optional[tuple[str, str]] = None
        self._condition = threading.Condition()
        self._shutdown = False
        self._register_events()

    def _register_events(self) -> None:
        @self.sio.on('cmd_login')
        def login(data):
            IRC_EVENTS.write('socket_command', name='cmd_login', data=data)
            username = str(data.get('username', '')).strip()
            password = str(data.get('password', '')).strip()
            if not username or not password:
                return
            with self._condition:
                self._credentials = (username, password)
                if self.active_client:
                    self.active_client.stop()
                self._condition.notify_all()

        @self.sio.on('cmd_logout')
        def logout(_data=None):
            IRC_EVENTS.write('socket_command', name='cmd_logout')
            with self._condition:
                self._credentials = None
                if self.active_client:
                    self.active_client.stop()
                self._condition.notify_all()
            self.sio.emit('irc_state', {'state': IRC_STATE_LOGGED_OUT, 'attempt': 0, 'retry_in': 0})

        @self.sio.on('cmd_reconnect')
        def reconnect(_data=None):
            IRC_EVENTS.write('socket_command', name='cmd_reconnect')
            if self.active_client:
                self.active_client.retryNow()

        @self.sio.on('bounce_send_msg')
        def send_message(data):
            if self.active_client:
                self.active_client.send_from_ui(data)

        @self.sio.on('bounce_tab_close')
        def remove_chat(data):
            if self.active_client:
                self.active_client.remove_chat(data)

        @self.sio.on('cmd_req_ch')
        def request_channel(data):
            if self.active_client:
                self.active_client.request_channel(data)

    def connect(self) -> None:
        while not self._shutdown and not self.sio.connected:
            try:
                self.sio.connect(self.server_url)
                IRC_EVENTS.write('ui_bridge_connected', url=self.server_url)
            except Exception:
                IRC_EVENTS.write('ui_bridge_retry', url=self.server_url)
                time.sleep(.25)

    def submit_credentials(self, username: str, password: str) -> None:
        if username and password:
            with self._condition:
                self._credentials = (username, password)
                self._condition.notify_all()

    def run(self) -> None:
        self.connect()
        while not self._shutdown:
            with self._condition:
                while self._credentials is None and not self._shutdown:
                    self._condition.wait()
                if self._shutdown:
                    break
                username, password = self._credentials

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            client = Client(
                token=password,
                nickname=username,
                logger=self.logger,
                sio=self.sio,
                Loop=loop
            )
            self.active_client = client
            client.run()
            self.active_client = None

            with self._condition:
                if self._credentials == (username, password):
                    self._credentials = None

    def shutdown(self) -> None:
        # commit suicide
        IRC_EVENTS.write('supervisor_shutdown')
        self._shutdown = True
        if self.active_client:
            self.active_client.stop()
        with self._condition:
            self._condition.notify_all()
        if self.sio.connected:
            self.sio.disconnect()
