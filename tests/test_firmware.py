# SPDX-License-Identifier: GPL-3.0-or-later
import os

import pytest

from resources.lib import efivars, esp, steamos
from resources.lib.constants import EFI_ROOT, EFIVARS_DIR

pytestmark = pytest.mark.firmware


@pytest.fixture(scope='module')
def firmware():
    machine = efivars.Firmware()
    if not os.path.isdir(EFI_ROOT):
        pytest.skip('no %s: this machine did not boot through UEFI'
                    % EFI_ROOT)
    if not os.path.isdir(EFIVARS_DIR):
        pytest.skip('no %s: the kernel is not exposing EFI variables'
                    % EFIVARS_DIR)
    if os.geteuid() != 0:
        pytest.skip('efivarfs is root-only; re-run this level as root')
    return machine


def test_this_machine_can_be_told_where_to_boot(firmware):
    assert firmware.problem() is None


def test_this_machines_entries_parse(firmware):
    entries = firmware.boot_entries()
    assert entries, 'no boot entries at all'
    for entry in entries:
        assert 0 <= entry.number <= 0xffff
        assert isinstance(entry.description, str)
        assert isinstance(entry.loader, str)


def test_every_entry_this_machine_boots_has_a_name(firmware):
    bootable = [entry for entry in firmware.boot_entries() if entry.bootable]
    assert bootable, 'nothing on this machine is bootable'
    assert all(entry.description for entry in bootable)


def test_the_boot_order_names_entries_that_exist(firmware):
    numbers = {entry.number for entry in firmware.boot_entries()}
    listed = [number for number in firmware.boot_order() if number in numbers]
    assert listed == [entry.number for entry in firmware.boot_entries()
                      if entry.number in set(firmware.boot_order())]


def test_the_running_system_is_one_of_the_entries(firmware):
    current = firmware.boot_current()
    if current is None:
        pytest.skip('this firmware does not publish BootCurrent')
    numbers = {entry.number for entry in firmware.boot_entries()}
    assert current in numbers


def test_detection_never_proposes_the_running_system(firmware):
    entries = firmware.boot_entries()
    current = firmware.boot_current()
    for candidate in steamos.candidates(entries, exclude=current):
        assert candidate.number != current


def test_what_this_machine_would_be_offered(firmware, capsys):
    entries = firmware.boot_entries()
    current = firmware.boot_current()
    partitions = firmware.present_partitions()
    steamos_esp = esp.steamos_partition(firmware.partlabels,
                                        firmware.partitions)
    with capsys.disabled():
        print('\n    BootCurrent %s   BootNext %s'
              % (current, firmware.boot_next()))
        for entry in entries:
            print('    %s  %-30s %-40s score=%d%s%s'
                  % (entry.name, entry.description[:30], entry.loader[:40],
                     steamos.score(entry, esp=steamos_esp),
                     '  <- running' if entry.number == current else '',
                     '  [partition not visible]'
                     if steamos.is_stale(entry, partitions) else ''))
        chosen = steamos.resolve(entries, exclude=current,
                                 partitions=partitions, esp=steamos_esp)
        print('    detected: %s' % (chosen.description if chosen else
                                    'nothing; the add-on would ask'))
