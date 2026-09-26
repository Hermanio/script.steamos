# SPDX-License-Identifier: GPL-3.0-or-later
import os
import re

_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _manifest_version():
    with open(os.path.join(_ROOT, 'addon.xml'), encoding='utf-8') as handle:
        match = re.search(r'<addon[^>]*?version="([\d.]+)"', handle.read(),
                          re.DOTALL)
    return match.group(1) if match else '0.0.0'


INFO = {
    'id': 'script.steamos',
    'name': 'Boot into SteamOS',
    'version': _manifest_version(),
    'path': _ROOT,
    'icon': os.path.join(_ROOT, 'icon.png'),
    'fanart': os.path.join(_ROOT, 'fanart.jpg'),
    'profile': os.path.join(_ROOT, 'tests', 'profile'),
}

STRINGS = {}


class Addon:
    def __init__(self, id=None):
        self.id = id or INFO['id']

    def getAddonInfo(self, key):
        return INFO.get(key, '')

    def getLocalizedString(self, string_id):
        return STRINGS.get(string_id, '')
