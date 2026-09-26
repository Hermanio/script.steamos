# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import os
import re
import xml.etree.ElementTree as ET

import pytest

from .conftest import ADDON_DIR

LIB_DIR = os.path.join(ADDON_DIR, 'resources', 'lib')
ENGLISH = 'resource.language.en_gb'
PO_ENTRY = re.compile(r'msgctxt "#(\d+)"\nmsgid "([^"]*)"\nmsgstr "([^"]*)"')


@pytest.fixture(scope='module')
def root():
    return ET.parse(os.path.join(ADDON_DIR, 'addon.xml')).getroot()


def read(*parts):
    with open(os.path.join(ADDON_DIR, *parts), encoding='utf-8') as handle:
        return handle.read()


def lib_modules():
    return sorted(name for name in os.listdir(LIB_DIR)
                  if name.endswith('.py') and name != '__init__.py')


def catalogue():
    return {int(ctx): (msgid, msgstr) for ctx, msgid, msgstr in
            PO_ENTRY.findall(read('resources', 'language', ENGLISH,
                                  'strings.po'))}


def imported_modules(name):
    for node in ast.walk(ast.parse(read('resources', 'lib', name))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module


def test_the_manifest_points_at_files_that_exist(root):
    assert root.get('id') == 'script.steamos'
    script = root.find("extension[@point='xbmc.python.script']")
    assert os.path.isfile(os.path.join(ADDON_DIR, script.get('library')))
    for node in root.find("extension[@point='xbmc.addon.metadata']/assets"):
        assert os.path.isfile(os.path.join(ADDON_DIR, node.text)), node.text


def test_it_declares_no_dependency_it_does_not_have(root):
    imports = {imp.get('addon') for imp in root.findall('requires/import')}
    assert imports == {'xbmc.python'}


def test_there_are_no_settings():
    assert not os.path.exists(os.path.join(ADDON_DIR, 'resources',
                                           'settings.xml'))
    for name in lib_modules():
        assert 'Setting' not in read('resources', 'lib', name), name


def test_only_bootnext_is_written():
    written = set(re.findall(r"_write\('(\w+)'",
                             read('resources', 'lib', 'efivars.py')))
    assert written == {'BootNext'}, written


def test_the_catalogue_defines_exactly_the_strings_the_code_uses():
    used = set()
    for name in lib_modules():
        used.update(int(i) for i in re.findall(
            r'localize\((\d+)', read('resources', 'lib', name)))
    assert set(catalogue()) == used


def test_english_is_the_source_language():
    for string_id, (msgid, msgstr) in catalogue().items():
        assert msgid and not msgstr, string_id


def test_only_kodiutils_touches_the_kodi_api():
    for name in lib_modules():
        touches = any(module.startswith('xbmc')
                      for module in imported_modules(name))
        assert touches == (name == 'kodiutils.py'), name


def test_the_firmware_layer_uses_the_standard_library_only():
    allowed = {'collections', 'fcntl', 'os', 're', 'struct'}
    for name in ('constants.py', 'efivars.py', 'esp.py', 'steamos.py'):
        for module in imported_modules(name):
            assert module.split('.')[0] in allowed, (name, module)


def test_nothing_shells_out_to_a_binary():
    for name in lib_modules():
        source = read('resources', 'lib', name)
        assert 'subprocess' not in source, name
        assert 'efibootmgr' not in source, name
        assert 'bootctl' not in source, name
