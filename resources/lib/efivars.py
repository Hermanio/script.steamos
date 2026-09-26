# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
import fcntl
import os
import re
import struct

from .constants import (BOOT_VARIABLE_ATTRIBUTES,
                        DEVICE_PATH_END_TYPE,
                        DEVICE_PATH_FILE_PATH_SUBTYPE,
                        DEVICE_PATH_HARD_DRIVE_SUBTYPE,
                        DEVICE_PATH_MEDIA_TYPE, EFI_ROOT, EFIVARS_DIR,
                        FS_IMMUTABLE_FL, GLOBAL_VARIABLE_GUID,
                        HARD_DRIVE_NODE_LENGTH, LOAD_OPTION_ACTIVE,
                        LOAD_OPTION_CATEGORY, LOAD_OPTION_CATEGORY_APP,
                        LOAD_OPTION_HIDDEN, PARTLABEL_DIR, PARTUUID_DIR,
                        PROBLEM_NOT_UEFI,
                        PROBLEM_NO_EFIVARS, PROBLEM_READ_ONLY,
                        SIGNATURE_TYPE_GUID)

BOOT_ENTRY_NAME = re.compile(
    r'^Boot([0-9A-Fa-f]{4})-%s$' % GLOBAL_VARIABLE_GUID, re.IGNORECASE)

ATTRIBUTE_HEADER = 4

_FLAGS_SIZE = struct.calcsize('=l')
_FS_IOC_GETFLAGS = (2 << 30) | (_FLAGS_SIZE << 16) | (ord('f') << 8) | 1
_FS_IOC_SETFLAGS = (1 << 30) | (_FLAGS_SIZE << 16) | (ord('f') << 8) | 2


class EfiError(Exception):
    pass


class BootEntry(collections.namedtuple(
        'BootEntry',
        'number description loader active hidden application partition')):
    __slots__ = ()

    @property
    def name(self):
        return 'Boot%04X' % self.number

    @property
    def bootable(self):
        return self.active and not self.application


def parse_load_option(number, data):
    if len(data) < 6:
        return None
    attributes, path_length = struct.unpack('<IH', data[:6])
    description, offset = read_utf16(data, 6)
    if description is None:
        return None
    device_path = data[offset:offset + path_length]
    return BootEntry(
        number=number,
        description=description,
        loader=device_path_file(device_path),
        active=bool(attributes & LOAD_OPTION_ACTIVE),
        hidden=bool(attributes & LOAD_OPTION_HIDDEN),
        application=(attributes & LOAD_OPTION_CATEGORY)
        == LOAD_OPTION_CATEGORY_APP,
        partition=device_path_partition(device_path))


def read_utf16(data, offset):
    index = offset
    while index + 1 < len(data):
        if data[index] == 0 and data[index + 1] == 0:
            return data[offset:index].decode('utf-16-le', 'replace'), index + 2
        index += 2
    return None, offset


def device_path_file(blob):
    found = []
    instance = []
    offset = 0
    while offset + 4 <= len(blob):
        node_type, sub_type, length = struct.unpack(
            '<BBH', blob[offset:offset + 4])
        if length < 4:
            break
        if node_type == DEVICE_PATH_END_TYPE:
            if instance:
                found = instance
                break
            offset += length
            continue
        if (node_type == DEVICE_PATH_MEDIA_TYPE
                and sub_type == DEVICE_PATH_FILE_PATH_SUBTYPE):
            text = blob[offset + 4:offset + length]
            instance.append(text.decode('utf-16-le', 'replace').rstrip('\x00'))
        offset += length
    return ''.join(found or instance)


def device_path_partition(blob):
    offset = 0
    while offset + 4 <= len(blob):
        node_type, sub_type, length = struct.unpack(
            '<BBH', blob[offset:offset + 4])
        if length < 4:
            break
        if (node_type == DEVICE_PATH_MEDIA_TYPE
                and sub_type == DEVICE_PATH_HARD_DRIVE_SUBTYPE
                and length >= HARD_DRIVE_NODE_LENGTH):
            node = blob[offset + 4:offset + HARD_DRIVE_NODE_LENGTH]
            if node[37] == SIGNATURE_TYPE_GUID:
                return format_guid(node[20:36])
        offset += length
    return ''


def format_guid(raw):
    first, second, third = struct.unpack('<IHH', raw[:8])
    return '%08x-%04x-%04x-%s-%s' % (first, second, third,
                                     raw[8:10].hex(), raw[10:16].hex())


def in_boot_order(entries, order):
    position = {number: index for index, number in enumerate(order)}
    return sorted(entries,
                  key=lambda entry: (position.get(entry.number, len(order)),
                                     entry.number))


def unlock(path):
    try:
        with open(path, 'rb') as handle:
            flags = struct.unpack('=l', fcntl.ioctl(
                handle, _FS_IOC_GETFLAGS, b'\0' * _FLAGS_SIZE))[0]
            if flags & FS_IMMUTABLE_FL:
                fcntl.ioctl(handle, _FS_IOC_SETFLAGS,
                            struct.pack('=l', flags & ~FS_IMMUTABLE_FL))
    except OSError:
        return


class Firmware:
    def __init__(self, root=EFI_ROOT, efivars=EFIVARS_DIR,
                 partitions=PARTUUID_DIR, partlabels=PARTLABEL_DIR):
        self.root = root
        self.efivars = efivars
        self.partitions = partitions
        self.partlabels = partlabels

    def present_partitions(self):
        try:
            return {name.lower() for name in os.listdir(self.partitions)}
        except OSError:
            return None

    def problem(self):
        if not os.path.isdir(self.root):
            return PROBLEM_NOT_UEFI
        if not os.path.isdir(self.efivars):
            return PROBLEM_NO_EFIVARS
        if not os.access(self.efivars, os.W_OK):
            return PROBLEM_READ_ONLY
        return None

    def boot_current(self):
        return self._uint16('BootCurrent')

    def boot_next(self):
        return self._uint16('BootNext')

    def boot_order(self):
        data = self._read('BootOrder') or b''
        usable = len(data) // 2 * 2
        return list(struct.unpack('<%dH' % (usable // 2), data[:usable]))

    def set_boot_next(self, number):
        self._write('BootNext', struct.pack('<H', number))

    def boot_entries(self):
        entries = []
        for name in self._variable_names():
            match = BOOT_ENTRY_NAME.match(name)
            if not match:
                continue
            entry = parse_load_option(
                int(match.group(1), 16),
                self._read_file(os.path.join(self.efivars, name)))
            if entry is not None:
                entries.append(entry)
        return in_boot_order(entries, self.boot_order())

    def _variable_names(self):
        try:
            return sorted(os.listdir(self.efivars))
        except OSError as exc:
            raise EfiError('%s: %s' % (self.efivars, exc))

    def _path(self, variable):
        return os.path.join(self.efivars,
                            '%s-%s' % (variable, GLOBAL_VARIABLE_GUID))

    def _read_file(self, path):
        try:
            with open(path, 'rb') as handle:
                return handle.read()[ATTRIBUTE_HEADER:]
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise EfiError('%s: %s' % (os.path.basename(path), exc))

    def _read(self, variable):
        return self._read_file(self._path(variable))

    def _uint16(self, variable):
        data = self._read(variable)
        if not data or len(data) < 2:
            return None
        return struct.unpack('<H', data[:2])[0]

    def _write(self, variable, data):
        path = self._path(variable)
        unlock(path)
        payload = struct.pack('<I', BOOT_VARIABLE_ATTRIBUTES) + data
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o644)
            try:
                os.write(descriptor, payload)
            finally:
                os.close(descriptor)
        except OSError as exc:
            raise EfiError('%s: %s' % (variable, exc))
