import unittest

from match_parser import parse_banchobot_message, parse_match_message


class MatchParserTests(unittest.TestCase):
    def test_team_username_preserves_punctuation_and_normalizes_spaces(self):
        event = parse_banchobot_message('-xxx Rumia- joined in slot 2 for team red.')
        self.assertIsNotNone(event)
        self.assertEqual('join_slot', event.kind)
        self.assertEqual('-xxx_Rumia-', event.username)
        self.assertEqual('red', event.team)

    def test_slot_username_accepts_punctuation(self):
        event = parse_banchobot_message(
            'Slot 3 https://osu.ppy.sh/u/12345 -xxx Rumia- [Ready / Team Blue]'
        )
        self.assertIsNotNone(event)
        self.assertEqual('-xxx_Rumia-', event.username)
        self.assertEqual('blue', event.team)
        h2h = parse_banchobot_message(
            'Slot 1 https://osu.ppy.sh/users/12345 Player Name [Ready / No Mod]'
        )
        self.assertEqual(('Player_Name', 'none'), (h2h.username, h2h.team))

    def test_match_creation_is_anchored(self):
        valid = parse_banchobot_message(
            'Created the tournament match https://osu.ppy.sh/mp/123456 Tourney: Team A vs Team B'
        )
        self.assertEqual('123456', valid.match_id)
        self.assertIsNone(parse_banchobot_message(
            'prefix Created the tournament match https://osu.ppy.sh/mp/123456 Tourney'
        ))

    def test_player_message_cannot_change_match_state(self):
        content = 'Victim changed to blue'
        self.assertIsNone(parse_match_message('MaliciousPlayer', content))
        self.assertEqual('change_team', parse_match_message('bAnChObOt', content).kind)

    def test_team_name_must_be_known_and_message_must_end(self):
        self.assertIsNone(parse_banchobot_message('Player changed to spectators'))
        self.assertIsNone(parse_banchobot_message('Player changed to red. injected text'))

    def test_settings_block_messages_are_parsed(self):
        room = parse_banchobot_message(
            'Room name: Finals, History: https://osu.ppy.sh/mp/121634110'
        )
        mode = parse_banchobot_message('Team mode: TeamVs, Win condition: ScoreV2')
        self.assertEqual(('121634110', 'Finals'), (room.match_id, room.match_name))
        self.assertEqual(('TeamVs', 'ScoreV2'), (mode.team, mode.value))
        self.assertEqual('players', parse_banchobot_message('Players: 4').kind)
        self.assertEqual('beatmap', parse_banchobot_message(
            'Beatmap: https://osu.ppy.sh/b/123 Artist - Title [Insane]'
        ).kind)
        self.assertEqual('mods', parse_banchobot_message('Active mods: HD, HR').kind)

    def test_match_timers_and_player_leaves_are_parsed(self):
        self.assertEqual(120, parse_banchobot_message('Countdown ends in 2 minutes').seconds)
        self.assertEqual(5, parse_banchobot_message('Match starts in 5 seconds').seconds)
        self.assertEqual('countdown_abort', parse_banchobot_message('Countdown aborted').kind)
        self.assertEqual('match_abort', parse_banchobot_message('Aborted the match').kind)
        left = parse_banchobot_message('-xxx Rumia- left the game.')
        self.assertEqual(('-xxx_Rumia-', 'leave'), (left.username, left.kind))

    def test_live_settings_slot_tracks_player_state(self):
        event = parse_banchobot_message(
            'Slot 1  Not Ready https://osu.ppy.sh/u/14566042 HijiriS         [Host / Team Red ]'
        )
        self.assertEqual(('HijiriS', 'red', 1), (event.username, event.team, event.slot))
        self.assertFalse(event.ready)
        self.assertTrue(event.host)
        h2h = parse_banchobot_message('HijiriS joined in slot 1.')
        self.assertEqual(('none', 1), (h2h.team, h2h.slot))

    def test_live_size_host_mod_and_map_messages_are_parsed(self):
        self.assertEqual(15, parse_banchobot_message('Changed match to size 15').size)
        self.assertEqual('all_ready', parse_banchobot_message('All players are ready').kind)
        self.assertEqual('HijiriS', parse_banchobot_message('HijiriS became the host.').username)
        self.assertEqual('clear_host', parse_banchobot_message('Cleared match host').kind)
        mods = parse_banchobot_message(
            'Enabled NoFail, Easy, DoubleTime, SpunOut, disabled FreeMod'
        )
        self.assertEqual(('mods', 'NoFail, Easy, DoubleTime, SpunOut'), (mods.kind, mods.value))
        beatmap = parse_banchobot_message(
            "Beatmap changed to: Feint - Drifters [Light Insane] (https://osu.ppy.sh/b/2524734)"
        )
        self.assertEqual(('2524734', 'Feint - Drifters [Light Insane]'), (
            beatmap.map_id, beatmap.value
        ))


if __name__ == '__main__':
    unittest.main()
