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


if __name__ == '__main__':
    unittest.main()
