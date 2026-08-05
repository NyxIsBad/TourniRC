import unittest

from tournaments import parse_mappool_text


class TournamentImporterTests(unittest.TestCase):
    def test_imports_three_line_map_groups_in_order(self):
        maps = parse_mappool_text('''
NM1
!mp mods 1
!mp map 4612267 0

FM1
!mp mods 1 freemod
!mp map 5077935 0
''')
        self.assertEqual(['NM1', 'FM1'], [item['designator'] for item in maps])
        self.assertEqual('!mp mods 1 freemod', maps[1]['mods_command'])
        self.assertEqual('!mp map 5077935 0', maps[1]['map_command'])
        self.assertEqual(5077935, maps[1]['map_id'])
        self.assertEqual('', maps[1]['name'])
        self.assertEqual([], maps[1]['mods'])

    def test_rejects_incomplete_groups_and_wrong_command_lines(self):
        with self.assertRaises(ValueError):
            parse_mappool_text('NM1\nmods\n')
        with self.assertRaises(ValueError):
            parse_mappool_text('NM1\nanything here\nstill rejected')

    def test_command_arguments_remain_opaque(self):
        maps = parse_mappool_text('NM1\n!mp mods whatever the tournament wants\n!mp map custom mode')
        self.assertEqual('!mp mods whatever the tournament wants', maps[0]['mods_command'])
        self.assertEqual('!mp map custom mode', maps[0]['map_command'])
        self.assertIsNone(maps[0]['map_id'])

    def test_imports_single_line_entries(self):
        maps = parse_mappool_text('NM1 !mp mods 1  !mp map 4612267 0')
        self.assertEqual('NM1', maps[0]['designator'])
        self.assertEqual('!mp mods 1', maps[0]['mods_command'])
        self.assertEqual('!mp map 4612267 0', maps[0]['map_command'])
        self.assertEqual(4612267, maps[0]['map_id'])

    def test_imports_multiple_entries_separated_only_by_spaces(self):
        maps = parse_mappool_text(
            'NM1 !mp mods 1 !mp map 4612267 0 '
            'HD1 !mp mods 9 !mp map 3792291 0'
        )
        self.assertEqual(['NM1', 'HD1'], [item['designator'] for item in maps])


if __name__ == '__main__':
    unittest.main()
