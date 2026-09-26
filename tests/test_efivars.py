# SPDX-License-Identifier: GPL-3.0-or-later
import os
import struct

import pytest

from resources.lib import efivars
from resources.lib.constants import (GLOBAL_VARIABLE_GUID,
                                     LOAD_OPTION_ACTIVE,
                                     LOAD_OPTION_CATEGORY_APP,
                                     LOAD_OPTION_HIDDEN, PROBLEM_NOT_UEFI,
                                     PROBLEM_NO_EFIVARS, PROBLEM_READ_ONLY)

from resources.lib.steamos import score as steamos_score

from .conftest import load_option, write_variable


def test_a_real_machines_entries_parse(fedora_efivars):
    entries = fedora_efivars.boot_entries()
    described = {entry.number: entry.description for entry in entries}
    assert described == {0x0000: 'BootManagerMenuApp',
                         0x0001: 'EFI Firmware Setup',
                         0x0002: 'UEFI Misc Device',
                         0x0003: 'Fedora'}


def test_a_real_loader_path_survives_the_device_path(fedora_efivars):
    fedora = [entry for entry in fedora_efivars.boot_entries()
              if entry.number == 3][0]
    assert fedora.loader == '\\EFI\\fedora\\shimx64.efi'


def test_entries_without_a_file_path_do_not_invent_one(fedora_efivars):
    entries = {entry.number: entry for entry in fedora_efivars.boot_entries()}
    assert entries[0x0000].loader == ''
    assert entries[0x0002].loader == ''


def test_firmware_tools_are_marked_as_applications(fedora_efivars):
    entries = {entry.number: entry for entry in fedora_efivars.boot_entries()}
    assert entries[0x0000].application and entries[0x0000].hidden
    assert entries[0x0001].application
    assert not entries[0x0003].application
    assert entries[0x0003].bootable


def test_a_real_boot_order_is_followed(fedora_efivars):
    assert [entry.number for entry in fedora_efivars.boot_entries()] == \
        [0x0003, 0x0002, 0x0000, 0x0001]
    assert fedora_efivars.boot_order() == [0x0003, 0x0002, 0x0000, 0x0001]
    assert fedora_efivars.boot_current() == 0x0003


def test_a_machine_with_no_bootnext_reads_as_none(fedora_efivars):
    assert fedora_efivars.boot_next() is None


def test_the_real_targets_entries_all_parse(libreelec_efivars):
    entries = libreelec_efivars.boot_entries()
    assert len(entries) == 13
    assert all(entry.description for entry in entries)


def test_a_loader_after_an_end_node_is_still_found(libreelec_efivars):
    entries = {entry.number: entry for entry in
               libreelec_efivars.boot_entries()}
    assert entries[0x0002].loader == '\\EFI\\STEAMOS\\STEAMCL.EFI'
    assert entries[0x0000].loader == \
        '\\EFI\\MICROSOFT\\BOOT\\BOOTMGFW.EFI'
    assert entries[0x0001].loader == '\\EFI\\FEDORA\\SHIMX64.EFI'


def test_libreelec_itself_boots_through_the_removable_fallback(
        libreelec_efivars):
    entries = {entry.number: entry for entry in
               libreelec_efivars.boot_entries()}
    assert entries[0x000c].description == 'UEFI OS'
    assert entries[0x000c].loader == '\\EFI\\BOOT\\BOOTX64.EFI'
    assert steamos_score(entries[0x000c]) == 0


def test_entries_that_are_hidden_are_still_bootable(libreelec_efivars):
    entries = libreelec_efivars.boot_entries()
    steamos_entries = [e for e in entries if e.description == 'SteamOS']
    assert steamos_entries
    assert all(entry.hidden for entry in steamos_entries)
    assert all(entry.bootable for entry in steamos_entries)


def test_optional_data_is_not_read_as_a_device_path(libreelec_efivars):
    entries = {entry.number: entry for entry in
               libreelec_efivars.boot_entries()}
    assert 'BCDOBJECT' not in entries[0x0000].loader
    assert entries[0x0000].loader.endswith('BOOTMGFW.EFI')


def test_setting_the_next_boot_can_be_read_back(dual_boot):
    dual_boot.set_boot_next(0x0001)
    assert dual_boot.boot_next() == 0x0001


def test_the_written_variable_is_shaped_the_way_the_kernel_expects(dual_boot):
    dual_boot.set_boot_next(0x0001)
    path = os.path.join(dual_boot.efivars,
                        'BootNext-%s' % GLOBAL_VARIABLE_GUID)
    with open(path, 'rb') as handle:
        blob = handle.read()
    assert len(blob) == 6
    attributes, number = struct.unpack('<IH', blob)
    assert attributes == 0x07
    assert number == 0x0001


def test_arming_twice_overwrites_rather_than_appends(dual_boot):
    dual_boot.set_boot_next(0x0001)
    dual_boot.set_boot_next(0x0000)
    assert dual_boot.boot_next() == 0x0000


def test_a_write_that_cannot_happen_raises_rather_than_lying(dual_boot):
    os.chmod(dual_boot.efivars, 0o555)
    try:
        with pytest.raises(efivars.EfiError):
            dual_boot.set_boot_next(0x0001)
    finally:
        os.chmod(dual_boot.efivars, 0o755)


def test_a_machine_without_uefi_says_so(tmp_path):
    firmware = efivars.Firmware(root=str(tmp_path / 'nothing'),
                                efivars=str(tmp_path / 'nothing' / 'efivars'))
    assert firmware.problem() == PROBLEM_NOT_UEFI


def test_uefi_without_efivarfs_is_a_different_problem(tmp_path):
    root = tmp_path / 'efi'
    root.mkdir()
    firmware = efivars.Firmware(root=str(root),
                                efivars=str(root / 'efivars'))
    assert firmware.problem() == PROBLEM_NO_EFIVARS


def test_efivars_that_cannot_be_written_is_reported_before_anything_else(
        dual_boot):
    assert dual_boot.problem() is None
    os.chmod(dual_boot.efivars, 0o555)
    try:
        assert dual_boot.problem() == PROBLEM_READ_ONLY
    finally:
        os.chmod(dual_boot.efivars, 0o755)


def test_a_healthy_machine_reports_no_problem(dual_boot):
    assert dual_boot.problem() is None


def test_other_variables_are_not_mistaken_for_boot_entries(dual_boot):
    write_variable(dual_boot.efivars, 'BootOptionSupport',
                   struct.pack('<I', 0x13))
    numbers = [entry.number for entry in dual_boot.boot_entries()]
    assert numbers == [0x0000, 0x0001]


def test_a_malformed_entry_does_not_hide_the_others(dual_boot):
    write_variable(dual_boot.efivars, 'Boot0009', b'\x01\x00')
    numbers = [entry.number for entry in dual_boot.boot_entries()]
    assert numbers == [0x0000, 0x0001]


def test_entries_missing_from_the_boot_order_are_still_listed(make_efivars):
    firmware = make_efivars(
        entries=[
            (0x0000, load_option('LibreELEC', '\\EFI\\BOOT\\BOOTX64.EFI')),
            (0x0005, load_option('SteamOS', '\\EFI\\steamos\\steamcl.efi')),
        ],
        order=[0x0000])
    assert [entry.number for entry in firmware.boot_entries()] == [0, 5]


def test_an_inactive_entry_is_listed_and_labelled(make_efivars):
    firmware = make_efivars(
        entries=[(0x0002, load_option('SteamOS',
                                      '\\EFI\\steamos\\steamcl.efi',
                                      attributes=0))])
    entry = firmware.boot_entries()[0]
    assert entry.active is False
    assert entry.bootable is False


def test_a_hidden_application_is_neither_active_nor_bootable(make_efivars):
    firmware = make_efivars(
        entries=[(0x0000, load_option(
            'Setup', attributes=LOAD_OPTION_ACTIVE | LOAD_OPTION_HIDDEN
            | LOAD_OPTION_CATEGORY_APP))])
    entry = firmware.boot_entries()[0]
    assert entry.hidden and entry.application and not entry.bootable


def test_a_multi_node_file_path_is_joined(dual_boot):
    split = (b'\x04\x04\x0e\x00' + '\\EFI'.encode('utf-16-le') + b'\x00\x00'
             + b'\x04\x04\x18\x00'
             + '\\steamcl.efi'.encode('utf-16-le')[:20] + b'\x00\x00'
             + b'\x7f\xff\x04\x00')
    option = struct.pack('<IH', 1, len(split)) + \
        'Split'.encode('utf-16-le') + b'\x00\x00' + split
    write_variable(dual_boot.efivars, 'Boot0007', option)
    entry = [e for e in dual_boot.boot_entries() if e.number == 7][0]
    assert entry.loader.startswith('\\EFI\\steamcl')


def test_the_name_of_an_entry_is_how_the_firmware_spells_it():
    entry = efivars.parse_load_option(0x000b, load_option('SteamOS'))
    assert entry.name == 'Boot000B'


def test_an_empty_device_path_parses_to_an_empty_loader():
    assert efivars.device_path_file(b'') == ''
    assert efivars.device_path_file(b'\x7f\xff\x04\x00') == ''


def test_a_device_path_with_a_zero_length_node_stops_rather_than_spins():
    assert efivars.device_path_file(b'\x04\x04\x00\x00' * 4) == ''


def test_the_ioctl_numbers_match_the_kernels_definitions():
    assert struct.calcsize('=l') in (4, 8)
    if struct.calcsize('=l') == 8:
        assert efivars._FS_IOC_GETFLAGS == 0x80086601
        assert efivars._FS_IOC_SETFLAGS == 0x40086602
    else:
        assert efivars._FS_IOC_GETFLAGS == 0x80046601
        assert efivars._FS_IOC_SETFLAGS == 0x40046602


def test_clearing_the_immutable_flag_is_survivable_everywhere(dual_boot,
                                                              tmp_path):
    efivars.unlock(str(tmp_path / 'never-created'))
    existing = os.path.join(dual_boot.efivars,
                            'BootOrder-%s' % GLOBAL_VARIABLE_GUID)
    efivars.unlock(existing)
    assert os.path.isfile(existing)


def test_the_partition_guid_is_read_from_the_device_path(libreelec_efivars):
    entries = {entry.number: entry for entry in
               libreelec_efivars.boot_entries()}
    assert entries[0x0002].partition == \
        'e7e707b0-aa7f-4f53-96b5-d8959cf658f7'
    assert entries[0x0003].partition == \
        '88d47368-85ee-4273-adc1-580f95aa2c00'


def test_every_steamos_install_named_a_different_partition(libreelec_efivars):
    steamos_entries = [entry for entry in libreelec_efivars.boot_entries()
                       if entry.description == 'SteamOS']
    partitions = [entry.partition for entry in steamos_entries]
    assert len(steamos_entries) == 7
    assert all(partitions)
    assert len(set(partitions)) == 7


def test_an_entry_with_no_hard_drive_node_names_no_partition(fedora_efivars):
    entries = {entry.number: entry for entry in fedora_efivars.boot_entries()}
    assert entries[0x0000].partition == ''
    assert entries[0x0003].partition == \
        '1f14754a-0441-472b-bfb7-fc467c3cd07d'


def test_an_mbr_signature_is_not_read_as_a_partition_guid():
    node = (b'\x04\x01\x2a\x00' + struct.pack('<IQQ', 1, 2048, 524288)
            + b'\xde\xad\xbe\xef' + b'\x00' * 12 + b'\x01\x01')
    assert efivars.device_path_partition(node + b'\x7f\xff\x04\x00') == ''


def test_the_partitions_a_machine_can_see_are_a_directory_listing(
        make_efivars):
    firmware = make_efivars(partitions=['AAAA-BBBB', 'cccc-dddd'])
    assert firmware.present_partitions() == {'aaaa-bbbb', 'cccc-dddd'}


def test_a_machine_that_cannot_be_asked_says_so_rather_than_nothing(
        dual_boot):
    assert dual_boot.present_partitions() is None
