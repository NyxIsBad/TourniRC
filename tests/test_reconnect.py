import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cfg import roomsConfig, userConfig
from osu_irc.Classes.client import Client
from osu_irc.Utils.detector import mainEventDetector
from osu_irc.Utils.errors import EmptyPayload, PingTimeout
from irclib import Client as TourniRCClient
from eventlog import _sanitize


class FakeReader:
    def __init__(self, payload=None, block=False):
        self.payload = payload
        self.block = block

    async def readline(self):
        if self.block:
            await asyncio.Future()
        return self.payload


class FakeWriter:
    def __init__(self):
        self.closed = False
        self.waited = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.waited = True


class FakeSocketIO:
    def __init__(self, state):
        self.state = state
        self.emitted = []

    def emit(self, name, data):
        self.emitted.append((name, data))

    def call(self, name, timeout=None):
        return self.state


class LifecycleClient(Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.events = []

    async def onReady(self):
        self.events.append('ready')

    async def onReconnect(self):
        self.events.append('reconnect')


class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_read_is_a_reconnectable_empty_payload(self):
        client = Client(Loop=asyncio.get_running_loop(), token='token', nickname='name')
        client.running = True
        client.ConnectionReader = FakeReader(b'')
        with self.assertRaises(EmptyPayload):
            await client.listen()

    async def test_blocked_read_becomes_ping_timeout(self):
        client = Client(
            Loop=asyncio.get_running_loop(), token='token', nickname='name', read_timeout=.01
        )
        client.running = True
        client.ConnectionReader = FakeReader(block=True)
        with self.assertRaises(PingTimeout):
            await client.listen()

    async def test_ready_then_reconnect_events_are_distinct(self):
        client = LifecycleClient(Loop=asyncio.get_running_loop(), token='token', nickname='name')
        ready = ':cho.ppy.sh 001 name :Welcome'
        self.assertTrue(await mainEventDetector(client, ready))
        self.assertEqual(['ready'], client.events)
        self.assertTrue(await mainEventDetector(client, ready))
        self.assertEqual(['ready', 'reconnect', 'ready'], client.events)

    async def test_backoff_is_capped(self):
        client = Client(Loop=asyncio.get_running_loop(), token='token', nickname='name')
        delays = [min(2 ** (attempt - 1), client.max_reconnect_delay) for attempt in range(1, 10)]
        self.assertEqual([1, 2, 4, 8, 16, 30, 30, 30, 30], delays)

    async def test_close_connection_closes_and_awaits_writer(self):
        client = Client(Loop=asyncio.get_running_loop(), token='token', nickname='name')
        writer = FakeWriter()
        client.ConnectionWriter = writer
        await client.closeConnection()
        self.assertTrue(writer.closed)
        self.assertTrue(writer.waited)
        self.assertIsNone(client.ConnectionWriter)

    async def test_reconnect_false_stops_after_first_failure(self):
        class NoReconnectClient(Client):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.disconnects = []

            async def onDisconnected(self, error, attempt, retry_delay):
                self.disconnects.append((attempt, retry_delay))

        client = NoReconnectClient(
            Loop=asyncio.get_running_loop(), token='token', nickname='name', reconnect=False
        )
        with patch('osu_irc.Classes.client.asyncio.open_connection', side_effect=OSError('offline')):
            await client.start()
        self.assertEqual([(0, 0)], client.disconnects)
        self.assertFalse(client.running)

    async def test_restore_rejoins_rooms_but_not_pm_tabs(self):
        state = {
            'chats': [
                {'channel': '#mp_123', 'type': 1},
                {'channel': 'BanchoBot', 'type': 2}
            ],
            'current_chat': '#mp_123'
        }
        sio = FakeSocketIO(state)
        client = TourniRCClient(
            Loop=asyncio.get_running_loop(), token='token', nickname='name',
            logger=__import__('logging').getLogger('test'), sio=sio
        )
        joined = []

        async def record_join(channel):
            joined.append(channel)

        client.joinChannel = record_join
        await client.onReady()
        self.assertEqual(['#mp_123'], joined)
        self.assertIn(('restore_tab', {'channel': '#mp_123'}), sio.emitted)


class UserConfigTests(unittest.TestCase):
    def test_credentials_round_trip_and_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'login.ini'
            config = userConfig(str(path))
            self.assertFalse(config.has_credentials())
            config.set_credentials('Referee', 'secret')
            loaded = userConfig(str(path))
            self.assertTrue(loaded.has_credentials())
            self.assertEqual('Referee', loaded.get_username())
            loaded.clear_credentials()
            self.assertFalse(userConfig(str(path)).has_credentials())

    def test_event_log_redacts_credentials_and_pass_commands(self):
        sanitized = _sanitize({
            'username': 'Referee',
            'password': 'secret',
            'nested': {'token': 'also-secret'},
            'raw': b'PASS secret\r\n'
        })
        self.assertEqual('[REDACTED]', sanitized['password'])
        self.assertEqual('[REDACTED]', sanitized['nested']['token'])
        self.assertEqual('PASS [REDACTED]', sanitized['raw'])


class UiSessionTests(unittest.TestCase):
    def setUp(self):
        import ui
        self.ui = ui
        self.original_user_cfg = ui.user_cfg
        self.original_rooms_cfg = ui.rms_cfg
        self.temp_dir = tempfile.TemporaryDirectory()
        ui.user_cfg = userConfig(str(Path(self.temp_dir.name) / 'login.ini'))
        ui.rms_cfg = roomsConfig(str(Path(self.temp_dir.name) / 'recentrooms.ini'))
        ui.chats.clear()
        ui.pending_credentials = None
        ui.connection_state.clear()
        ui.connection_state.update({'state': ui.IRC_STATE_LOGGED_OUT, 'attempt': 0, 'retry_in': 0})
        self.client = ui.socketio.test_client(ui.app)

    def tearDown(self):
        self.client.disconnect()
        self.ui.user_cfg = self.original_user_cfg
        self.ui.rms_cfg = self.original_rooms_cfg
        self.temp_dir.cleanup()

    def test_login_validates_and_persists_credentials(self):
        self.client.emit('login_submit', {'username': '', 'password': ''})
        results = [x for x in self.client.get_received() if x['name'] == 'login_result']
        self.assertFalse(results[-1]['args'][0]['ok'])

        self.client.emit('login_submit', {'username': 'Referee', 'password': 'secret'})
        results = [x for x in self.client.get_received() if x['name'] == 'login_result']
        self.assertTrue(results[-1]['args'][0]['ok'])
        self.assertFalse(self.ui.user_cfg.has_credentials())
        self.client.emit('irc_state', {'state': self.ui.IRC_STATE_AUTHENTICATED})
        self.assertTrue(self.ui.user_cfg.has_credentials())

    def test_session_snapshot_preserves_room_types_and_selection(self):
        with patch.object(self.ui, 'emit'):
            self.ui.chats.add_chat('#mp_123', 1)
            self.ui.chats.add_chat('BanchoBot', 2)
        self.ui.chats.set_current_chat('#mp_123')
        snapshot = self.client.emit('session_state', callback=True)
        self.assertEqual('#mp_123', snapshot['current_chat'])
        self.assertEqual(
            [{'channel': '#mp_123', 'type': 1}, {'channel': 'BanchoBot', 'type': 2}],
            snapshot['chats']
        )

    def test_send_is_rejected_while_disconnected(self):
        self.client.get_received()
        self.client.emit('send_msg', {'content': 'do not send'})
        received = self.client.get_received()
        self.assertTrue(any(event['name'] == 'notif' for event in received))
        self.assertFalse(any(event['name'] == 'bounce_send_msg' for event in received))


if __name__ == '__main__':
    unittest.main()
