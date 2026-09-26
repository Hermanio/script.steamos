# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import json
import os
import struct
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(TESTS_DIR)
STUBS_DIR = os.path.join(TESTS_DIR, 'stubs')
FIXTURES_DIR = os.path.join(TESTS_DIR, 'fixtures')

for path in (STUBS_DIR, ADDON_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from resources.lib.constants import (BOOT_VARIABLE_ATTRIBUTES,
                                     GLOBAL_VARIABLE_GUID,
                                     LOAD_OPTION_ACTIVE)

MEDIA_FILE_PATH_NODE = b'\x04\x04'
HARD_DRIVE_NODE = b'\x04\x01\x2a\x00'
END_NODE = b'\x7f\xff\x04\x00'


def hard_drive(partition):
    first, second, third = partition.split('-')[:3]
    tail = bytes.fromhex(''.join(partition.split('-')[3:]))
    signature = (struct.pack('<IHH', int(first, 16), int(second, 16),
                             int(third, 16)) + tail)
    return (HARD_DRIVE_NODE + struct.pack('<IQQ', 1, 2048, 524288)
            + signature + b'\x02\x02')


def load_fixture(name):
    return {name: base64.b64decode(blob)
            for name, blob in read_fixture(name)['variables'].items()}


def read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as handle:
        return json.load(handle)


def load_option(description, loader='', attributes=LOAD_OPTION_ACTIVE,
                partition=''):
    device_path = hard_drive(partition) if partition else b''
    if loader:
        encoded = loader.encode('utf-16-le') + b'\x00\x00'
        device_path += (MEDIA_FILE_PATH_NODE
                        + struct.pack('<H', len(encoded) + 4) + encoded)
    device_path += END_NODE
    return (struct.pack('<IH', attributes, len(device_path))
            + description.encode('utf-16-le') + b'\x00\x00'
            + device_path)


def write_variable(directory, name, data,
                   attributes=BOOT_VARIABLE_ATTRIBUTES):
    path = os.path.join(directory, '%s-%s' % (name, GLOBAL_VARIABLE_GUID))
    with open(path, 'wb') as handle:
        handle.write(struct.pack('<I', attributes) + data)
    return path


@pytest.fixture
def make_efivars(tmp_path):
    from resources.lib.efivars import Firmware

    def build(entries=(), order=None, current=None, variables=None,
              partitions=None, partlabels=None):
        root = tmp_path / 'efi'
        efivars = root / 'efivars'
        efivars.mkdir(parents=True)
        partitions_dir = tmp_path / 'by-partuuid'
        if partitions is not None:
            partitions_dir.mkdir()
            for partition in partitions:
                (partitions_dir / partition).write_text('')
        for number, data in entries:
            write_variable(str(efivars), 'Boot%04X' % number, data)
        for name, blob in (variables or {}).items():
            path = efivars / ('%s-%s' % (name, GLOBAL_VARIABLE_GUID))
            path.write_bytes(blob)
        if order is not None:
            write_variable(str(efivars), 'BootOrder',
                           struct.pack('<%dH' % len(order), *order))
        if current is not None:
            write_variable(str(efivars), 'BootCurrent',
                           struct.pack('<H', current))
        label_dir = tmp_path / 'by-partlabel'
        if partlabels is not None:
            label_dir.mkdir()
            for label, partition in partlabels.items():
                (label_dir / label).symlink_to(partitions_dir / partition)
        return Firmware(root=str(root), efivars=str(efivars),
                        partitions=str(partitions_dir),
                        partlabels=str(label_dir))

    return build


@pytest.fixture
def dual_boot(make_efivars):
    return make_efivars(
        entries=[
            (0x0000, load_option('LibreELEC', '\\EFI\\BOOT\\BOOTX64.EFI')),
            (0x0001, load_option('SteamOS', '\\EFI\\steamos\\steamcl.efi')),
        ],
        order=[0x0000, 0x0001],
        current=0x0000)


@pytest.fixture
def fedora_efivars(make_efivars):
    return make_efivars(variables=load_fixture('efivars-fedora.json'))


@pytest.fixture
def libreelec_efivars(make_efivars):
    return make_efivars(variables=load_fixture('efivars-libreelec.json'))


@pytest.fixture
def libreelec_as_it_really_was(make_efivars):
    recorded = read_fixture('efivars-libreelec.json')
    return make_efivars(
        variables={name: base64.b64decode(blob)
                   for name, blob in recorded['variables'].items()},
        partitions=recorded['partitions'],
        partlabels=recorded['partlabels'])


@pytest.fixture(autouse=True)
def clean_kodi_state():
    import xbmc
    import xbmcgui

    xbmc.reset()
    xbmcgui.reset()
    yield
    xbmc.reset()
    xbmcgui.reset()
