# SPDX-License-Identifier: GPL-3.0-or-later
import os

import xbmc
import xbmcgui

from resources.lib import main
from resources.lib.constants import (LOAD_OPTION_ACTIVE,
                                     LOAD_OPTION_CATEGORY_APP,
                                     PROBLEM_NOT_UEFI)

from .conftest import load_option, write_variable


def rebooted():
    return 'Reboot' in xbmc.BUILTINS


def armed(firmware):
    return firmware.boot_next()


def choose(index):
    xbmcgui.SELECT_ANSWERS.append(index)


def stopped_with():
    return xbmcgui.OK_DIALOGS[0][1] if xbmcgui.OK_DIALOGS else ''


def test_launching_it_arms_steamos_and_reboots(dual_boot):
    main.run(dual_boot)
    assert armed(dual_boot) == 0x0001
    assert rebooted()
    assert not xbmcgui.OK_DIALOGS


def test_the_real_target_machine_just_goes(libreelec_efivars):
    main.run(libreelec_efivars)
    assert rebooted()
    assert not xbmcgui.OK_DIALOGS
    chosen = [entry for entry in libreelec_efivars.boot_entries()
              if entry.number == armed(libreelec_efivars)][0]
    assert chosen.description == 'SteamOS'
    assert chosen.loader == '\\EFI\\STEAMOS\\STEAMCL.EFI'


def test_the_machine_as_it_really_was_arms_the_entry_that_works(
        libreelec_as_it_really_was):
    main.run(libreelec_as_it_really_was)
    assert armed(libreelec_as_it_really_was) == 0x000C
    assert rebooted()
    assert not xbmcgui.OK_DIALOGS


def test_the_seven_decoys_lose_to_the_partition_table(
        libreelec_as_it_really_was):
    main.run(libreelec_as_it_really_was)
    chosen = [entry for entry in libreelec_as_it_really_was.boot_entries()
              if entry.number == armed(libreelec_as_it_really_was)][0]
    assert chosen.description == 'UEFI OS'
    assert 'steamcl' not in chosen.loader.lower()


def test_the_real_target_machine_takes_the_firmwares_first_choice(
        libreelec_efivars):
    main.run(libreelec_efivars)
    assert armed(libreelec_efivars) == 0x0002


def test_it_never_writes_anything_but_bootnext(dual_boot):
    before = set(os.listdir(dual_boot.efivars))
    main.run(dual_boot)
    after = set(os.listdir(dual_boot.efivars))
    added = {name.split('-')[0] for name in after - before}
    assert added == {'BootNext'}


def test_an_ambiguous_machine_asks(make_efivars):
    firmware = make_efivars(
        entries=[(0, load_option('SteamOS', '\\EFI\\steamos\\steamcl.efi')),
                 (1, load_option('SteamOS spare',
                                 '\\EFI\\steamos-b\\steamcl.efi'))],
        order=[0, 1])
    choose(1)
    main.run(firmware)
    assert xbmcgui.SELECT_DIALOGS
    assert armed(firmware) == 1
    assert rebooted()


def test_backing_out_of_the_choice_changes_nothing(make_efivars):
    firmware = make_efivars(
        entries=[(0, load_option('SteamOS', '\\EFI\\steamos\\steamcl.efi')),
                 (1, load_option('SteamOS spare',
                                 '\\EFI\\steamos-b\\steamcl.efi'))],
        order=[0, 1])
    main.run(firmware)
    assert armed(firmware) is None
    assert not rebooted()
    assert not xbmcgui.OK_DIALOGS


def test_each_row_names_the_entry_its_number_and_its_disk(make_efivars):
    firmware = make_efivars(
        entries=[(2, load_option('SteamOS', '\\EFI\\steamos\\steamcl.efi',
                                 partition='aaaa0000-0000-0000-0000-'
                                           '000000000001')),
                 (5, load_option('SteamOS spare',
                                 '\\EFI\\steamos-b\\steamcl.efi',
                                 partition='bbbb0000-0000-0000-0000-'
                                           '000000000002'))],
        order=[2, 5],
        partitions=['aaaa0000-0000-0000-0000-000000000001',
                    'bbbb0000-0000-0000-0000-000000000002'],
        partlabels={'esp': 'aaaa0000-0000-0000-0000-000000000001',
                    'data': 'bbbb0000-0000-0000-0000-000000000002'})
    choose(0)
    main.run(firmware)
    _heading, rows = xbmcgui.SELECT_DIALOGS[0]
    assert rows[0].startswith('0002')
    assert 'SteamOS' in rows[0]
    assert '(esp)' in rows[0]


def test_an_inactive_entry_is_offered_and_labelled(make_efivars):
    firmware = make_efivars(
        entries=[(2, load_option('Rescue', '\\EFI\\rescue\\boot.efi')),
                 (5, load_option('SteamOS spare',
                                 '\\EFI\\steamos\\steamcl.efi',
                                 attributes=0))],
        order=[2, 5])
    choose(0)
    main.run(firmware)
    _heading, rows = xbmcgui.SELECT_DIALOGS[0]
    assert len(rows) == 2
    assert 'inactive' in rows[-1]
    assert rows[-1].startswith('0005')


def test_an_inactive_entry_is_never_armed_on_its_own(make_efivars):
    firmware = make_efivars(
        entries=[(2, load_option('LibreELEC', '\\EFI\\BOOT\\BOOTX64.EFI')),
                 (5, load_option('SteamOS', '\\EFI\\steamos\\steamcl.efi',
                                 attributes=0))],
        order=[2, 5], current=2)
    main.run(firmware)
    assert firmware.boot_next() is None
    assert xbmcgui.SELECT_DIALOGS


def test_a_firmware_application_is_never_offered(make_efivars):
    firmware = make_efivars(
        entries=[(2, load_option('Rescue', '\\EFI\\rescue\\boot.efi')),
                 (5, load_option('EFI Firmware Setup',
                                 attributes=LOAD_OPTION_ACTIVE
                                 | LOAD_OPTION_CATEGORY_APP))],
        order=[2, 5])
    choose(0)
    main.run(firmware)
    _heading, rows = xbmcgui.SELECT_DIALOGS[0]
    assert len(rows) == 1
    assert rows[0].startswith('0002')


def test_a_dead_entry_is_offered_last_and_labelled(make_efivars):
    firmware = make_efivars(
        entries=[(2, load_option('SteamOS', '\\EFI\\steamos\\steamcl.efi',
                                 partition='dead0000-0000-0000-0000-'
                                           '000000000001')),
                 (5, load_option('Other', '\\EFI\\other\\boot.efi',
                                 partition='beef0000-0000-0000-0000-'
                                           '000000000002'))],
        order=[2, 5],
        partitions=['beef0000-0000-0000-0000-000000000002'])
    choose(0)
    main.run(firmware)
    _heading, rows = xbmcgui.SELECT_DIALOGS[0]
    assert 'partition not visible' in rows[-1]
    assert rows[-1].startswith('0002')


def test_a_machine_with_nothing_bootable_says_so(make_efivars):
    firmware = make_efivars(
        entries=[(0, load_option('LibreELEC', '\\EFI\\BOOT\\BOOTX64.EFI'))],
        order=[0], current=0)
    main.run(firmware)
    assert armed(firmware) is None
    assert not rebooted()
    assert not xbmcgui.SELECT_DIALOGS
    assert stopped_with()


def test_anything_bootable_is_offered_even_if_it_is_not_steamos(make_efivars):
    firmware = make_efivars(
        entries=[(0, load_option('LibreELEC', '\\EFI\\BOOT\\BOOTX64.EFI')),
                 (1, load_option('Windows', '\\EFI\\win\\bootmgfw.efi'))],
        order=[0, 1], current=0)
    choose(0)
    main.run(firmware)
    _heading, rows = xbmcgui.SELECT_DIALOGS[0]
    assert len(rows) == 1
    assert 'Windows' in rows[0]


def test_a_machine_without_uefi_is_told_why_not(tmp_path):
    from resources.lib.efivars import Firmware

    firmware = Firmware(root=str(tmp_path / 'none'),
                        efivars=str(tmp_path / 'none' / 'efivars'))
    assert firmware.problem() == PROBLEM_NOT_UEFI
    main.run(firmware)
    assert 'UEFI' in stopped_with()
    assert not rebooted()


def test_kodi_without_root_is_told_that_is_the_problem(dual_boot):
    os.chmod(dual_boot.efivars, 0o555)
    try:
        main.run(dual_boot)
    finally:
        os.chmod(dual_boot.efivars, 0o755)
    assert 'root' in stopped_with()
    assert not rebooted()


def test_a_firmware_with_no_entries_at_all_is_not_a_crash(make_efivars):
    firmware = make_efivars()
    main.run(firmware)
    assert stopped_with()
    assert not rebooted()


def test_a_firmware_that_drops_bootnext_does_not_get_a_reboot(dual_boot,
                                                              monkeypatch):
    monkeypatch.setattr(type(dual_boot), 'boot_next', lambda self: None)
    main.run(dual_boot)
    assert not rebooted()
    assert stopped_with()


def test_a_write_that_fails_is_reported_rather_than_rebooted(dual_boot,
                                                             monkeypatch):
    from resources.lib import efivars

    def refuse(self, number):
        raise efivars.EfiError('no')

    monkeypatch.setattr(type(dual_boot), 'set_boot_next', refuse)
    main.run(dual_boot)
    assert not rebooted()
    assert stopped_with()


def test_unreadable_boot_variables_are_reported_rather_than_raised(
        dual_boot, monkeypatch):
    from resources.lib import efivars

    def refuse(self):
        raise efivars.EfiError('no')

    monkeypatch.setattr(type(dual_boot), 'boot_entries', refuse)
    main.run(dual_boot)
    assert stopped_with()
    assert not rebooted()


def test_every_failure_is_logged_before_it_is_shown(dual_boot):
    main.run(make_broken(dual_boot))
    assert [line for level, line in xbmc.LOG if level == xbmc.LOGERROR]


def make_broken(firmware):
    for name in os.listdir(firmware.efivars):
        os.remove(os.path.join(firmware.efivars, name))
    return firmware


def test_a_malformed_entry_beside_a_good_one_still_reaches_steamos(dual_boot):
    write_variable(dual_boot.efivars, 'Boot0004', b'\x01')
    main.run(dual_boot)
    assert armed(dual_boot) == 0x0001
