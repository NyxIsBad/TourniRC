from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def parse_beatmap_metadata(value):
    metadata = {}
    section = None
    for line in value.decode('utf-8-sig', errors='replace').splitlines():
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            section = line
            continue
        if section == '[Metadata]' and ':' in line:
            key, content = line.split(':', 1)
            metadata[key] = content.strip()
    artist = metadata.get('ArtistUnicode') or metadata.get('Artist')
    title = metadata.get('TitleUnicode') or metadata.get('Title')
    version = metadata.get('Version')
    if not artist or not title or not version:
        raise ValueError('beatmap metadata was incomplete.')
    return {'name': f'{artist} - {title} [{version}]'}


def fetch_beatmap_metadata(map_id, opener=urlopen):
    try:
        map_id = int(map_id)
        if map_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError('enter a positive osu! map ID first.')
    request = Request(
        f'https://osu.ppy.sh/osu/{map_id}',
        headers={'User-Agent': 'TourniRC/1.0', 'Range': 'bytes=0-131071'}
    )
    try:
        with opener(request, timeout=8) as response:
            content = response.read(128 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise ValueError('osu! did not return metadata for this map.')
    return {'map_id': map_id, **parse_beatmap_metadata(content)}
