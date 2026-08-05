import unittest

from tournaments import fetch_beatmap_metadata, parse_beatmap_metadata


class Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, _):
        return self.value


class TournamentMetadataTests(unittest.TestCase):
    def test_parses_unicode_map_name_and_difficulty(self):
        metadata = parse_beatmap_metadata(b'''osu file format v14
[Metadata]
Title:Title
TitleUnicode:Unicode Title
Artist:Artist
ArtistUnicode:Unicode Artist
Creator:Mapper
Version:Insane
''')
        self.assertEqual('Unicode Artist - Unicode Title [Insane]', metadata['name'])

    def test_fetch_uses_public_beatmap_file_and_returns_id(self):
        requests = []

        def opener(request, timeout):
            requests.append((request.full_url, timeout, request.get_header('Range')))
            return Response(b'[Metadata]\nTitle:Song\nArtist:Artist\nVersion:Hard\n')

        metadata = fetch_beatmap_metadata('4612267', opener)
        self.assertEqual(('https://osu.ppy.sh/osu/4612267', 8, 'bytes=0-131071'), requests[0])
        self.assertEqual({'map_id': 4612267, 'name': 'Artist - Song [Hard]'}, metadata)

    def test_rejects_invalid_ids_and_incomplete_metadata(self):
        with self.assertRaises(ValueError):
            fetch_beatmap_metadata('nope')
        with self.assertRaises(ValueError):
            parse_beatmap_metadata(b'[Metadata]\nTitle:Missing artist\n')


if __name__ == '__main__':
    unittest.main()
