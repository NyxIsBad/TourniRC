import json
import tempfile
import unittest
from pathlib import Path

from settings import DEFAULT_ALIASES, DEFAULT_HOTKEYS, SettingsError, SettingsRepository
from sounds import matching_sounds


class SettingsRepositoryTests(unittest.TestCase):
    def repository(self, directory):
        root = Path(directory)
        return SettingsRepository(root / 'settings.json')

    def test_defaults_are_persistent_and_do_not_customize_banchobot(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory)
            self.assertEqual(5, repository.data['chat']['room_history_limit'])
            self.assertEqual(DEFAULT_ALIASES, repository.data['controls']['aliases'])
            self.assertNotIn('banchobot', json.dumps(repository.data).casefold())
            self.assertEqual(repository.data, self.repository(directory).data)

    def test_theme_and_room_limit_are_owned_by_settings_json(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory)
            appearance = repository.snapshot()['appearance']; appearance['theme'] = 'cupcake'
            chat = repository.snapshot()['chat']; chat['room_history_limit'] = 9
            repository.update_section('appearance', appearance)
            repository.update_section('chat', chat)
            loaded = self.repository(directory)
            self.assertEqual('cupcake', loaded.data['appearance']['theme'])
            self.assertEqual(9, loaded.data['chat']['room_history_limit'])
            self.assertNotIn('schema_version', loaded.data)

    def test_bad_json_is_preserved_and_replaced_with_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('{nope', encoding='utf-8')
            repository = self.repository(directory)
            self.assertEqual(5, repository.data['chat']['room_history_limit'])
            self.assertEqual(1, len(list(Path(directory).glob('settings.invalid-*.json'))))

    def test_resets_preserve_user_data_owned_by_other_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory)
            controls = repository.snapshot()['controls']
            controls['aliases'] = {'/hello': '/query'}
            controls['hotkeys'] = {'next_tab': 'Ctrl+N'}
            controls['macros'] = [{
                'name': 'Abort', 'command': '!mp abort', 'alias': '/abort',
                'hotkey': '', 'button': True, 'confirm': True
            }]
            repository.update_section('controls', controls)
            repository.reset_section('controls')
            self.assertEqual(DEFAULT_ALIASES, repository.data['controls']['aliases'])
            self.assertEqual(DEFAULT_HOTKEYS, repository.data['controls']['hotkeys'])
            self.assertEqual('Abort', repository.data['controls']['macros'][0]['name'])

    def test_duplicate_macro_shortcuts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory)
            controls = repository.snapshot()['controls']
            controls['macros'] = [{
                'name': 'Collision', 'command': '!mp abort', 'alias': '',
                'hotkey': 'Alt+1', 'button': False, 'confirm': False
            }]
            with self.assertRaises(SettingsError):
                repository.update_section('controls', controls)

    def test_settings_ui_renders_alias_slash_as_a_fixed_prefix(self):
        template = (Path(__file__).parents[1] / 'templates' / 'settings.html').read_text(encoding='utf-8')
        self.assertIn("prefix.textContent = '/'", template)
        self.assertIn("alias ? `/${alias}` : ''", template)
        self.assertIn("replace(/^\\/+/, '')", template)


class SoundTriggerTests(unittest.TestCase):
    def settings(self, trigger):
        return {'audio': {'volume': .5, 'muted': False, 'assets': [], 'triggers': [trigger]}}

    def test_literal_sender_and_scope_filters(self):
        trigger = {
            'enabled': True, 'mode': 'literal', 'pattern': 'ready',
            'case_sensitive': False, 'sender': 'Bancho Bot', 'scope': 'match',
            'asset_id': 'builtin:nice.mp3'
        }
        settings = self.settings(trigger)
        self.assertEqual(1, len(matching_sounds(settings, 'Bancho_Bot', 'READY!', '#mp_1', 1)))
        self.assertEqual([], matching_sounds(settings, 'Player', 'ready', '#mp_1', 1))
        self.assertEqual([], matching_sounds(settings, 'Bancho_Bot', 'ready', 'BanchoBot', 2))

    def test_regex_and_mute_are_supported(self):
        trigger = {
            'enabled': True, 'mode': 'regex', 'pattern': r'^match .* finished$',
            'case_sensitive': False, 'sender': '', 'scope': 'all',
            'asset_id': 'builtin:nice.mp3'
        }
        settings = self.settings(trigger)
        self.assertEqual(1, len(matching_sounds(settings, 'BanchoBot', 'Match has FINISHED', '#mp_1', 1)))
        settings['audio']['muted'] = True
        self.assertEqual([], matching_sounds(settings, 'BanchoBot', 'Match has finished', '#mp_1', 1))


if __name__ == '__main__':
    unittest.main()
