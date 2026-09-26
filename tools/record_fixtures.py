# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import base64
import binascii
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resources.lib.constants import EFIVARS_DIR, GLOBAL_VARIABLE_GUID
from resources.lib.efivars import BOOT_ENTRY_NAME

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'tests', 'fixtures')

WANTED = ('BootOrder', 'BootCurrent', 'BootNext')


def read_efivars(directory):
    variables = {}
    for name in sorted(os.listdir(directory)):
        variable, _, guid = name.rpartition('-')
        if guid.lower() != GLOBAL_VARIABLE_GUID:
            continue
        if not (BOOT_ENTRY_NAME.match(name) or variable in WANTED):
            continue
        with open(os.path.join(directory, name), 'rb') as handle:
            variables[variable] = base64.b64encode(
                handle.read()).decode('ascii')
    return variables


HEX = re.compile(r'^(?:[0-9a-fA-F]{2})+$')


def decode(text):
    if len(text) % 2 == 0 and HEX.match(text):
        return binascii.unhexlify(text)
    return base64.b64decode(text)


def read_pasted(path):
    variables = {}
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            parts = line.split()
            if len(parts) == 2 and parts[0][:4] == 'Boot':
                variables[parts[0]] = base64.b64encode(
                    decode(parts[1])).decode('ascii')
    return variables


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="record this machine's EFI boot variables "
                    'as a test fixture')
    parser.add_argument('--name', required=True,
                        help='fixture name, e.g. steamdeck')
    parser.add_argument('--machine', default='',
                        help='one line describing the machine')
    parser.add_argument('--recorded', default='',
                        help='the date, YYYY-MM-DD')
    parser.add_argument('--from', dest='pasted',
                        help='a file of `Boot0000 <base64>` lines')
    parser.add_argument('--efivars', default=EFIVARS_DIR)
    args = parser.parse_args(argv)

    if args.pasted:
        variables = read_pasted(args.pasted)
    elif not os.path.isdir(args.efivars):
        parser.error('%s does not exist; pass --from instead' % args.efivars)
    else:
        variables = read_efivars(args.efivars)

    if not variables:
        parser.error('no boot variables found')

    path = os.path.join(FIXTURES_DIR, 'efivars-%s.json' % args.name)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump({'machine': args.machine,
                   'recorded': args.recorded,
                   'variables': variables},
                  handle, indent=2, sort_keys=True)
        handle.write('\n')
    print('wrote %s (%d variables)' % (path, len(variables)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
