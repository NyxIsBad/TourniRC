import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cfg import roomsConfig, uiConfig, userConfig
from osu_irc.Classes.client import Client
from osu_irc.Classes.user import User
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


class QuitClient(Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.quit_events = []

    async def onMemberQuit(self, user, reason):
        self.quit_events.append((user.name, reason))


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

    async def test_global_quit_for_unknown_user_is_ignored(self):
        client = QuitClient(Loop=asyncio.get_running_loop(), token='token', nickname='name')
        self.assertTrue(await mainEventDetector(client, ':Unrelated!cho@ppy.sh QUIT :quit'))
        await asyncio.sleep(0)
        self.assertEqual([], client.quit_events)

    async def test_quit_for_tracked_user_is_emitted_and_removed(self):
        client = QuitClient(Loop=asyncio.get_running_loop(), token='token', nickname='name')
        user = User(None)
        user._name = 'TrackedUser'
        client.users[user.name] = user
        self.assertTrue(await mainEventDetector(client, ':TrackedUser!cho@ppy.sh QUIT :quit'))
        await asyncio.sleep(0)
        self.assertEqual([('TrackedUser', 'quit')], client.quit_events)
        self.assertNotIn('TrackedUser', client.users)

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

    def test_recent_rooms_are_filtered_limited_and_case_insensitive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recentrooms.ini'
            config = roomsConfig(str(path), max_rooms=2)
            config.add_room('BanchoBot')
            config.add_room('#MP_One')
            config.add_room('#mp_one')
            config.add_room('#mp_two')
            config.add_room('#mp_three')
            self.assertEqual(['#mp_two', '#mp_three'], config.rooms)
            config.remove_room('#MP_TWO')
            self.assertEqual(['#mp_three'], config.rooms)
            self.assertEqual(['#mp_three'], roomsConfig(str(path), max_rooms=2).rooms)

    def test_recent_room_limit_is_clamped_and_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recentrooms.ini'
            config = roomsConfig(str(path))
            config.set_max_rooms(2)
            config.add_room('#one')
            config.add_room('#two')
            config.add_room('#three')
            loaded = roomsConfig(str(path))
            self.assertEqual(2, loaded.max_rooms)
            self.assertEqual(['#two', '#three'], loaded.rooms)
            loaded.set_max_rooms(999)
            self.assertEqual(50, loaded.max_rooms)

    def test_theme_is_written_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ui.ini'
            config = uiConfig(str(path))
            config.set_theme('cupcake')
            self.assertEqual('cupcake', config.theme)
            self.assertEqual('cupcake', uiConfig(str(path)).get_theme())

    def test_chat_template_uses_dom_nodes_for_untrusted_message_data(self):
        template = (Path(__file__).parents[1] / 'templates' / 'chat.html').read_text(encoding='utf-8')
        self.assertIn('appendMessageContent(content_element, content)', template)
        self.assertIn('user_element.textContent = `${user}:`', template)
        self.assertNotIn('${urlify(content)}', template)
        self.assertNotIn('aria-label="${data.channel}"', template)
        self.assertIn('message_list.length > 0', template)
        self.assertIn("setupChannelHotkeys(getTabs)", template)
        self.assertIn("tab_input.dataset.channel = data.channel", template)
        self.assertIn("window.addEventListener('backend_ready'", template)
        self.assertIn('resetChatSession()', template)
        self.assertIn("socket.emit(tag, { channel: channel }, function(data)", template)
        self.assertIn("selected.dataset.channel.toLowerCase() !== data.channel.toLowerCase()", template)
        self.assertIn("open.textContent = 'Open'", template)
        self.assertIn('https://osu.ppy.sh/mp/${encodeURIComponent(match_id)}', template)
        self.assertNotIn('pinned', template.lower())

        layout = (Path(__file__).parents[1] / 'templates' / 'layout.html').read_text(encoding='utf-8')
        self.assertIn("socket.on('disconnect'", layout)
        self.assertIn("socket.on('connect_error'", layout)
        self.assertIn('scheduleBackendUnavailable', layout)
        self.assertIn('}, 1500);', layout)
        self.assertIn('LOCAL SESSION LOST:', layout)
        self.assertIn('document.cookie = `theme=${encodeURIComponent(theme)}', layout)


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

    def test_backend_identity_is_stable_for_the_ui_process(self):
        self.client.emit('backend_identity_request')
        first = [
            event['args'][0]['instance_id'] for event in self.client.get_received()
            if event['name'] == 'backend_identity'
        ]
        self.client.emit('backend_identity_request')
        second = [
            event['args'][0]['instance_id'] for event in self.client.get_received()
            if event['name'] == 'backend_identity'
        ]
        self.assertTrue(first[0])
        self.assertEqual(first[0], second[0])

    def test_send_is_rejected_while_disconnected(self):
        self.client.get_received()
        self.client.emit('send_msg', {'content': 'do not send'})
        received = self.client.get_received()
        self.assertTrue(any(event['name'] == 'notif' for event in received))
        self.assertFalse(any(event['name'] == 'bounce_send_msg' for event in received))

    def test_chat_identity_is_case_insensitive(self):
        with patch.object(self.ui, 'emit'):
            self.ui.chats.add_chat('#MP_123', 1)
            self.ui.chats.add_chat('#mp_123', 1)
            self.ui.chats.set_current_chat('#Mp_123')
        self.assertEqual(1, self.ui.chats.chat_count)
        self.assertEqual('#MP_123', self.ui.chats.current_chat)
        self.assertIs(
            self.ui.chats.get_chat('#mp_123'),
            self.ui.chats.get_chat('#MP_123')
        )

    def test_unread_notifies_once_and_clears_on_swap(self):
        with patch.object(self.ui, 'emit'):
            self.ui.chats.add_chat('#one', 1)
            self.ui.chats.add_chat('#two', 1)
            self.ui.chats.set_current_chat('#one')
        self.client.get_received()
        message = {
            'user_name': 'Player',
            'room_name': 'two',
            'content': 'hello',
            'channel_type': 1,
            'time_recv': 1.0
        }
        self.client.emit('recv_msg', message.copy())
        first = self.client.get_received()
        self.assertTrue(any(event['name'] == 'tab_unread' for event in first))
        self.assertTrue(any(event['name'] == 'notif' for event in first))
        self.client.emit('recv_msg', message.copy())
        second = self.client.get_received()
        self.assertFalse(any(event['name'] == 'tab_unread' for event in second))
        self.assertFalse(any(event['name'] == 'notif' for event in second))
        self.assertTrue(self.ui.chats.get_chat('#two').unread)
        self.client.emit('tab_swap', {'channel': '#TWO'}, callback=True)
        self.assertFalse(self.ui.chats.get_chat('#two').unread)

    def test_alias_and_tab_order_are_display_state_only(self):
        with patch.object(self.ui, 'emit'):
            self.ui.chats.add_chat('#one', 1)
            self.ui.chats.add_chat('#two', 1)
        self.client.get_received()
        self.client.emit('change_alias', {'channel': '#ONE', 'alias': 'First Match'})
        events = self.client.get_received()
        self.assertEqual('First Match', self.ui.chats.get_chat('#one').alias)
        self.assertTrue(any(event['name'] == 'alias_changed' for event in events))
        self.client.emit('tab_reorder', {'channels': ['#TWO', '#one']})
        self.assertEqual(['#two', '#one'], self.ui.chats.channel_names)
        self.assertEqual('#one', self.ui.chats.get_chat('#ONE').channel_name)

    def test_reopening_aliased_room_selects_existing_tab(self):
        with patch.object(self.ui, 'emit'):
            self.ui.chats.add_chat('#mp_123', 1)
        self.client.get_received()
        self.client.emit('change_alias', {'channel': '#mp_123', 'alias': 'Finals'})
        self.client.get_received()
        self.client.emit('recent_room_open', {'channel': '#MP_123'})
        events = self.client.get_received()
        restored = [event for event in events if event['name'] == 'restore_tab']
        self.assertEqual({'channel': '#mp_123'}, restored[-1]['args'][0])
        self.assertFalse(any(event['name'] == 'cmd_req_ch' for event in events))
        self.assertEqual(1, self.ui.chats.chat_count)
        self.assertEqual('Finals', self.ui.chats.get_chat('#mp_123').alias)

    def test_channel_info_is_contextual(self):
        match = self.ui.Chat('#mp_123', 1)
        private = self.ui.Chat('BanchoBot', 2)
        channel = self.ui.Chat('#osu', 1)
        self.assertEqual('https://osu.ppy.sh/mp/123', match.channel_info()['url'])
        self.assertEqual('https://osu.ppy.sh/users/BanchoBot', private.channel_info()['url'])
        self.assertIsNone(channel.channel_info()['url'])
        self.assertEqual(('match', 'pm', 'channel'), (
            match.channel_info()['kind'],
            private.channel_info()['kind'],
            channel.channel_info()['kind']
        ))

    def test_match_state_tracks_players_settings_and_timer_priority(self):
        chat = self.ui.Chat('#mp_123', 1)
        with patch.object(self.ui, 'emit'):
            chat.team_change('Player', self.ui.TEAM_RED)
        chat.match_name = 'Finals'
        chat.team_mode = 'TeamVs'
        chat.win_condition = 'ScoreV2'
        chat.beatmap = 'Artist - Title [Insane]'
        chat.mods = 'HD, HR'
        chat.set_active_timer('match_timer', 120, 1000)
        chat.set_active_timer('start_timer', 5, 1001)
        self.assertEqual(1006, chat.timer_ends_at)
        self.assertEqual('start_timer', chat.active_timer)
        self.assertEqual(1, chat.channel_info()['player_count'])
        chat.remove_player('player')
        self.assertEqual({}, chat.teams)

    def test_player_mods_and_slot_moves_follow_banchobot(self):
        with patch.object(self.ui, 'emit'):
            self.ui.chats.add_chat('#mp_123', 1)

        def receive(content):
            self.client.emit('recv_msg', {
                'user_name': 'BanchoBot',
                'room_name': 'mp_123',
                'content': content,
                'channel_type': 1,
                'time_recv': 1000
            })

        receive('Active mods: Freemod')
        receive('Players: 1')
        receive('Slot 1  Not Ready https://osu.ppy.sh/u/10 Player One         ')
        chat = self.ui.chats.get_chat('#mp_123')
        self.assertEqual('NoMod', chat.players['Player_One']['mods'])
        receive('Slot 1  Not Ready https://osu.ppy.sh/u/10 Player One         [NoFail, Hidden]')
        self.assertEqual('NoFail, Hidden', chat.players['Player_One']['mods'])
        receive('Player One moved to slot 3')
        self.assertEqual(3, chat.players['Player_One']['slot'])
        receive('Active mods: NoFail, SpunOut')
        self.assertEqual('NoFail, SpunOut', chat.players['Player_One']['mods'])

    def test_banchobot_messages_update_match_state(self):
        with patch.object(self.ui, 'emit'):
            self.ui.chats.add_chat('#mp_123', 1)

        def receive(content, received_at=1000):
            self.client.emit('recv_msg', {
                'user_name': 'BanchoBot',
                'room_name': 'mp_123',
                'content': content,
                'channel_type': 1,
                'time_recv': received_at
            })

        receive('Room name: Finals, History: https://osu.ppy.sh/mp/123')
        receive('Team mode: TeamVs, Win condition: ScoreV2')
        receive('Players: 1')
        receive('Slot 1  Not Ready https://osu.ppy.sh/users/10 Player Name [Host / Team Red ]')
        receive('All players are ready')
        receive('Changed match to size 2')
        receive('Countdown ends in 2 minutes')
        receive('Match starts in 5 seconds', 1001)
        chat = self.ui.chats.get_chat('#mp_123')
        self.assertEqual(('Finals', 'TeamVs', 'ScoreV2'), (
            chat.match_name, chat.team_mode, chat.win_condition
        ))
        self.assertEqual({'Player_Name': self.ui.TEAM_RED}, chat.teams)
        self.assertTrue(chat.players['Player_Name']['ready'])
        self.assertTrue(chat.players['Player_Name']['host'])
        self.assertEqual(2, chat.match_size)
        self.assertEqual(('start_timer', 1006), (chat.active_timer, chat.timer_ends_at))
        receive('Aborted the match', 1002)
        self.assertIsNone(chat.active_timer)
        self.assertTrue(any(
            event['name'] == 'match_state' for event in self.client.get_received()
        ))

    def test_set_match_updates_state_without_sending_settings(self):
        with patch.object(self.ui, 'emit'):
            self.ui.chats.add_chat('#mp_123', 1)
        self.ui.connection_state['state'] = self.ui.IRC_STATE_AUTHENTICATED
        self.client.get_received()
        self.client.emit('recv_msg', {
            'user_name': 'BanchoBot',
            'room_name': 'mp_123',
            'content': 'Changed match settings to TeamVs, ScoreV2',
            'channel_type': 1,
            'time_recv': 1000
        })
        chat = self.ui.chats.get_chat('#mp_123')
        self.assertEqual(('TeamVs', 'ScoreV2'), (chat.team_mode, chat.win_condition))
        self.assertFalse(any(
            event['name'] == 'bounce_send_msg' for event in self.client.get_received()
        ))

    def test_recent_room_controls_update_config(self):
        self.ui.rms_cfg.add_room('#one')
        self.ui.rms_cfg.add_room('#two')
        self.client.get_received()
        self.client.emit('recent_room_open', {'channel': '#ONE'})
        opened = self.client.get_received()
        self.assertTrue(any(event['name'] == 'cmd_req_ch' for event in opened))
        self.client.emit('recent_room_remove', {'channel': '#ONE'})
        self.assertEqual(['#two'], self.ui.rms_cfg.rooms)
        self.client.emit('recent_rooms_limit', {'limit': '12'})
        self.assertEqual(12, self.ui.rms_cfg.max_rooms)
        self.client.emit('recent_rooms_clear')
        self.assertEqual([], self.ui.rms_cfg.rooms)

    def test_malformed_socket_payloads_are_ignored(self):
        malformed_events = [
            ('theme', None),
            ('nickname', {}),
            ('tab_open', {'channel': '#mp_1'}),
            ('send_msg', None),
            ('recv_msg', {'user_name': 'BanchoBot'}),
            ('tab_swap', {}),
            ('tab_close', None),
            ('irc_state', {'state': 'invented'}),
            ('set_timer', {}),
            ('set_match_timer', None),
            ('change_alias', {'channel': '#missing'})
        ]
        for name, payload in malformed_events:
            with self.subTest(name=name):
                self.client.emit(name, payload)

    def test_irc_bridge_rejects_malformed_commands(self):
        sio = FakeSocketIO({})
        client = TourniRCClient(
            Loop=asyncio.new_event_loop(), token='token', nickname='name',
            logger=__import__('logging').getLogger('test'), sio=sio
        )
        try:
            client.send_from_ui(None)
            client.remove_chat(None)
            client.request_channel(None)
        finally:
            client.Loop.close()


if __name__ == '__main__':
    unittest.main()
