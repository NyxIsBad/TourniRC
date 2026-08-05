import json
import copy
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from tournaments import MODS, TournamentAssignments, TournamentError, TournamentRepository, new_tournament, validate_tournament


def valid_tournament(name='Cup'):
    item = new_tournament(name)
    pool_id = str(uuid.uuid4())
    pick_id = str(uuid.uuid4())
    item['mappools'][pool_id] = {
        'id': pool_id, 'name': 'Finals', 'map_order': [pick_id],
        'maps': {pick_id: {
            'id': pick_id, 'designator': 'NM1', 'mods': ['NF', 'NM'],
            'name': 'Artist - Title [Insane]', 'map_id': 123,
            'map_command': '!mp map 123', 'mods_command': '!mp mods NF'
        }}
    }
    item['mappool_order'] = [pool_id]
    return item


class TournamentRepositoryTests(unittest.TestCase):
    def test_drafts_round_trip_but_cannot_enable(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = TournamentRepository(directory)
            draft = repository.create()
            self.assertFalse(draft['valid'])
            with self.assertRaises(TournamentError):
                repository.set_enabled(True)
            self.assertEqual(draft['id'], TournamentRepository(directory).get(draft['id'])['id'])

    def test_valid_presets_enable_and_duplicate_with_stable_new_id(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = TournamentRepository(directory)
            saved = repository.save(valid_tournament())
            self.assertTrue(saved['valid'])
            self.assertTrue(repository.set_enabled(True))
            duplicate = repository.duplicate(saved['id'])
            self.assertNotEqual(saved['id'], duplicate['id'])
            self.assertTrue(TournamentRepository(directory).enabled)

    def test_disabling_preserves_presets_and_reenabling_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = TournamentRepository(directory)
            repository.save(valid_tournament())
            repository.set_enabled(True)
            repository.set_enabled(False)
            self.assertFalse(TournamentRepository(directory).enabled)
            self.assertEqual(1, len(repository.items))

    def test_names_are_case_insensitively_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = TournamentRepository(directory)
            repository.save(valid_tournament('OWC'))
            with self.assertRaises(TournamentError):
                repository.save(valid_tournament('owc'))

    def test_malformed_presets_are_backed_up_and_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            presets = Path(directory) / 'presets'
            presets.mkdir(parents=True)
            (presets / 'bad.json').write_text('{bad', encoding='utf-8')
            repository = TournamentRepository(directory)
            self.assertEqual([], repository.list())
            self.assertEqual(1, len(list(presets.glob('bad.invalid-*.json'))))

    def test_validation_rejects_bad_order(self):
        item = valid_tournament()
        pool = next(iter(item['mappools'].values()))
        beatmap = next(iter(pool['maps'].values()))
        pool['map_order'] = []
        errors = validate_tournament(item)
        self.assertTrue(any('map order' in error for error in errors))

    def test_repository_rejects_non_uuid_ids_and_filename_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = TournamentRepository(directory)
            item = valid_tournament()
            item['id'] = '..\\outside'
            with self.assertRaises(TournamentError):
                repository.save(item)
            preset = valid_tournament()
            wrong_name = str(uuid.uuid4())
            path = Path(directory) / 'presets' / f'{wrong_name}.json'
            path.write_text(json.dumps(preset), encoding='utf-8')
            loaded = TournamentRepository(directory)
            self.assertNotIn(preset['id'], loaded.items)

    def test_commands_are_opaque_user_owned_strings(self):
        item = valid_tournament()
        beatmap = next(iter(next(iter(item['mappools'].values()))['maps'].values()))
        self.assertEqual([], validate_tournament(item))
        beatmap['map_command'] = 'custom tournament command format'
        beatmap['mods_command'] = 'also custom'
        self.assertEqual([], validate_tournament(item))
        beatmap.pop('map_command')
        beatmap.pop('mods_command')
        self.assertTrue(any('map command' in error for error in validate_tournament(item)))
        self.assertTrue(any('mods command' in error for error in validate_tournament(item)))

    def test_map_name_id_and_display_mods_are_optional(self):
        item = valid_tournament()
        beatmap = next(iter(next(iter(item['mappools'].values()))['maps'].values()))
        beatmap.pop('name')
        beatmap.pop('map_id')
        beatmap.pop('mods')
        self.assertEqual([], validate_tournament(item))

    def test_tournament_triggers_use_the_common_regex_validation(self):
        item = valid_tournament()
        item['sound_triggers'] = [{
            'name': 'bad regex', 'mode': 'regex', 'pattern': '(',
            'scope': 'match', 'asset_id': 'builtin:nice.mp3'
        }]
        self.assertTrue(any('regular expression' in error for error in validate_tournament(item)))

    def test_mod_multipliers_require_every_mod_and_positive_numbers(self):
        item = valid_tournament()
        self.assertEqual(set(MODS), set(item['score_calculation']['mod_multipliers']))
        item['score_calculation']['mod_multipliers']['NF'] = ''
        self.assertTrue(any('above zero' in error for error in validate_tournament(item)))
        item['score_calculation']['mod_multipliers']['NF'] = 0
        self.assertTrue(any('above zero' in error for error in validate_tournament(item)))
        item['score_calculation']['mod_multipliers']['NF'] = 0.5
        item['score_calculation']['mod_multipliers'].pop('HD')
        self.assertTrue(any('every mod' in error for error in validate_tournament(item)))

    def test_validation_covers_metadata_pools_and_required_map_fields(self):
        cases = []
        for change in (
            lambda item: item.update(color='purple'),
            lambda item: item.update(timer=0),
            lambda item: item.update(start_timer=''),
            lambda item: item.update(mappools={}, mappool_order=[]),
        ):
            item = valid_tournament(); change(item); cases.append(item)
        for item in cases:
            self.assertTrue(validate_tournament(item))

        item = valid_tournament()
        pool = next(iter(item['mappools'].values()))
        original = next(iter(pool['maps'].values()))
        duplicate = copy.deepcopy(original)
        duplicate['id'] = str(uuid.uuid4())
        pool['maps'][duplicate['id']] = duplicate
        pool['map_order'].append(duplicate['id'])
        self.assertTrue(any('duplicate designator' in error for error in validate_tournament(item)))

        item = valid_tournament()
        pool = next(iter(item['mappools'].values()))
        duplicate_pool = copy.deepcopy(pool)
        duplicate_pool['id'] = str(uuid.uuid4())
        item['mappools'][duplicate_pool['id']] = duplicate_pool
        item['mappool_order'].append(duplicate_pool['id'])
        self.assertTrue(any('mappool names' in error for error in validate_tournament(item)))

        for field in ('map_command', 'mods_command'):
            item = valid_tournament()
            next(iter(next(iter(item['mappools'].values()))['maps'].values()))[field] = ' '
            self.assertTrue(any(field.replace('_', ' ') in error for error in validate_tournament(item)))

        item = valid_tournament()
        next(iter(next(iter(item['mappools'].values()))['maps'].values()))['map_id'] = -1
        self.assertTrue(any('invalid map id' in error for error in validate_tournament(item)))

    def test_delete_removes_only_the_selected_uuid_file(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = TournamentRepository(directory)
            first = repository.save(valid_tournament('First'))
            second = repository.save(valid_tournament('Second'))
            repository.delete(first['id'])
            self.assertIsNone(repository.get(first['id']))
            self.assertIsNotNone(repository.get(second['id']))
            self.assertFalse((Path(directory) / 'presets' / f'{first["id"]}.json').exists())
            self.assertTrue((Path(directory) / 'presets' / f'{second["id"]}.json').exists())

    def test_failed_atomic_replacement_preserves_the_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = TournamentRepository(directory)
            saved = repository.save(valid_tournament('Original'))
            changed = copy.deepcopy(saved)
            changed.pop('valid'); changed.pop('errors')
            changed['name'] = 'Changed'
            with patch('tournaments.repository.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    repository.save(changed)
            loaded = TournamentRepository(directory).get(saved['id'])
            self.assertEqual('Original', loaded['name'])

    def test_invalid_persisted_enablement_is_disabled_on_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'presets').mkdir(parents=True)
            (root / 'state.json').write_text('{"enabled": true}', encoding='utf-8')
            repository = TournamentRepository(root)
            self.assertFalse(repository.enabled)
            self.assertFalse(json.loads((root / 'state.json').read_text(encoding='utf-8'))['enabled'])


class TournamentAssignmentTests(unittest.TestCase):
    def test_assignments_are_match_only_and_reset_pool_on_change(self):
        assignments = TournamentAssignments()
        with self.assertRaises(ValueError):
            assignments.assign('BanchoBot', 'one')
        assignments.assign('#MP_1', 'one')
        assignments.select_pool('#mp_1', 'finals')
        self.assertEqual('finals', assignments.get('#MP_1')['pool_id'])
        assignments.assign('#mp_1', 'two')
        self.assertIsNone(assignments.get('#mp_1')['pool_id'])


if __name__ == '__main__':
    unittest.main()
