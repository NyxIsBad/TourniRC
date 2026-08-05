class TournamentAssignments:
    def __init__(self):
        self._items = {}

    @staticmethod
    def key(channel):
        return str(channel).casefold()

    def get(self, channel):
        return dict(self._items.get(self.key(channel), {'tournament_id': None, 'pool_id': None}))

    def assign(self, channel, tournament_id):
        if not str(channel).casefold().startswith('#mp_'):
            raise ValueError('tournaments can only be assigned to match rooms.')
        self._items[self.key(channel)] = {'tournament_id': tournament_id or None, 'pool_id': None}
        return self.get(channel)

    def select_pool(self, channel, pool_id):
        item = self._items.get(self.key(channel))
        if not item or not item['tournament_id']:
            raise ValueError('assign a tournament first.')
        item['pool_id'] = pool_id or None
        return self.get(channel)

    def remove(self, channel):
        self._items.pop(self.key(channel), None)

    def clear_tournament(self, tournament_id):
        affected = [channel for channel, item in self._items.items() if item['tournament_id'] == tournament_id]
        for channel in affected:
            self._items.pop(channel)
        return affected

    def channels_for(self, tournament_id):
        return [channel for channel, item in self._items.items() if item['tournament_id'] == tournament_id]
