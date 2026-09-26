# SPDX-License-Identifier: GPL-3.0-or-later
from resources.lib import efivars, steamos

from .conftest import load_option


def entry(number, description, loader='', **kwargs):
    return efivars.parse_load_option(number,
                                     load_option(description, loader,
                                                 **kwargs))


STEAMOS = entry(1, 'SteamOS', '\\EFI\\steamos\\steamcl.efi')
LIBREELEC = entry(0, 'LibreELEC', '\\EFI\\BOOT\\BOOTX64.EFI')
WINDOWS = entry(2, 'Windows Boot Manager',
                '\\EFI\\Microsoft\\Boot\\bootmgfw.efi')


def test_the_valve_chainloader_is_the_strongest_signal():
    assert steamos.score(STEAMOS) == steamos.SCORE_LOADER
    assert steamos.score(entry(3, 'Games', '\\EFI\\steamos\\steamcl.efi')) == \
        steamos.SCORE_LOADER


def test_a_steamos_directory_counts_even_with_another_loader():
    renamed = entry(3, 'Gaming', '\\EFI\\steamos\\grubx64.efi')
    assert steamos.score(renamed) == steamos.SCORE_PATH


def test_a_description_is_the_weakest_signal_and_still_a_signal():
    assert steamos.score(entry(3, 'SteamOS Holo', '\\EFI\\holo\\boot.efi')) \
        == steamos.SCORE_DESCRIPTION


def test_a_system_that_is_not_steamos_scores_nothing():
    assert steamos.score(LIBREELEC) == 0
    assert steamos.score(WINDOWS) == 0


def test_matching_ignores_case_and_the_path_separator():
    assert steamos.score(entry(3, 'x', '/EFI/SteamOS/STEAMCL.EFI')) == \
        steamos.SCORE_LOADER
    assert steamos.score(entry(3, 'STEAMOS')) == steamos.SCORE_DESCRIPTION


def test_one_obvious_candidate_is_the_answer():
    assert steamos.resolve([LIBREELEC, STEAMOS]) == STEAMOS


def test_a_stronger_signal_beats_a_weaker_one_outright():
    weak = entry(4, 'SteamOS recovery', '\\EFI\\BOOT\\BOOTX64.EFI')
    assert steamos.resolve([weak, STEAMOS]) == STEAMOS


def test_two_different_candidates_are_not_determined():
    second = entry(5, 'SteamOS (B)', '\\EFI\\steamos-b\\steamcl.efi')
    assert steamos.resolve([STEAMOS, second]) is None


def test_nothing_that_looks_like_steamos_is_not_determined():
    assert steamos.resolve([LIBREELEC, WINDOWS]) is None


def test_the_running_system_is_never_the_answer():
    holo = entry(7, 'SteamOS', '\\EFI\\steamos\\steamcl.efi')
    assert steamos.resolve([holo], exclude=7) is None
    assert steamos.candidates([holo, STEAMOS], exclude=7) == [STEAMOS]


def test_firmware_applications_are_never_candidates():
    setup = entry(9, 'SteamOS Setup', attributes=0x0101)
    assert steamos.candidates([setup]) == []
    assert steamos.resolve([setup]) is None


def test_an_inactive_entry_is_not_a_candidate():
    dormant = entry(9, 'SteamOS', '\\EFI\\steamos\\steamcl.efi', attributes=0)
    assert steamos.candidates([dormant]) == []


def test_candidates_come_back_best_first():
    weak = entry(4, 'SteamOS recovery')
    middling = entry(5, 'Gaming', '\\EFI\\steamos\\grubx64.efi')
    ranked = steamos.candidates([weak, STEAMOS, middling, LIBREELEC])
    assert ranked == [STEAMOS, middling, weak]


def test_equal_candidates_keep_the_firmwares_own_order():
    second = entry(5, 'SteamOS (B)', '\\EFI\\steamos-b\\steamcl.efi')
    assert steamos.candidates([second, STEAMOS]) == [second, STEAMOS]


def clone(number, description='SteamOS',
          loader='\\EFI\\STEAMOS\\STEAMCL.EFI', partition=''):
    return entry(number, description, loader, partition=partition)


def test_identical_candidates_are_decided_by_the_firmwares_order():
    seven = [clone(n) for n in (2, 6, 4, 8, 0x0b, 3, 7)]
    assert steamos.resolve(seven) == seven[0]


def test_candidates_that_read_differently_are_not_determined():
    pair = [clone(2), clone(5, description='SteamOS (old disk)')]
    assert steamos.resolve(pair) is None


def test_one_identical_group_beside_a_different_one_is_not_determined():
    entries = [clone(n) for n in (2, 3, 4, 6, 7, 8)]
    entries.append(clone(0x0b, loader='\\EFI\\steamos-b\\steamcl.efi'))
    assert steamos.resolve(entries) is None


def test_exactly_one_live_partition_settles_a_tie():
    live = clone(2, partition='aaaaaaaa-0000-0000-0000-000000000001')
    dead = clone(3, partition='bbbbbbbb-0000-0000-0000-000000000002')
    present = {'aaaaaaaa-0000-0000-0000-000000000001'}
    assert steamos.resolve([dead, live], partitions=present) == live


def test_an_entry_on_a_partition_that_is_gone_is_never_the_answer():
    stale = clone(2, partition='aaaa0000-0000-0000-0000-000000000001')
    assert steamos.resolve([stale], partitions=set()) is None


def test_every_candidate_stale_means_it_cannot_decide():
    seven = [clone(n, partition='%08x-0000-0000-0000-000000000000' % n)
             for n in (2, 6, 4, 8, 0x0b, 3, 7)]
    assert steamos.resolve(seven, partitions={'something-else'}) is None


def test_a_live_entry_beside_stale_ones_is_still_the_answer():
    seven = [clone(n, partition='%08x-0000-0000-0000-000000000000' % n)
             for n in (2, 6, 4, 8, 0x0b, 3, 7)]
    assert steamos.resolve(
        seven, partitions={'00000008-0000-0000-0000-000000000000'}) == seven[3]


def test_unknown_partitions_still_rule_nothing_out():
    seven = [clone(n, partition='%08x-0000-0000-0000-000000000000' % n)
             for n in (2, 6, 4, 8, 0x0b, 3, 7)]
    assert steamos.resolve(seven, partitions=None) == seven[0]


def test_nothing_is_stale_when_the_question_could_not_be_asked():
    stale = clone(3, partition='bbbbbbbb-0000-0000-0000-000000000002')
    assert steamos.is_stale(stale, None) is False


def test_an_entry_naming_no_partition_is_never_stale():
    assert steamos.is_stale(entry(3, 'SteamOS'), set()) is False


ESP = 'e8ba5129-d543-4f4b-b523-af35b1264e1b'


def test_the_steamos_efi_partition_outranks_every_name():
    real = entry(0x0C, 'UEFI OS', '\\EFI\\BOOT\\BOOTX64.EFI',
                 partition=ESP)
    decoy = clone(2, partition='dead0000-0000-0000-0000-000000000001')
    assert steamos.score(real, esp=ESP) == steamos.SCORE_ESP
    assert steamos.score(real) == 0
    assert steamos.resolve([decoy, real], esp=ESP) == real


def test_without_the_partition_table_the_names_still_decide():
    real = entry(0x0C, 'UEFI OS', '\\EFI\\BOOT\\BOOTX64.EFI',
                 partition=ESP)
    plain = entry(2, 'SteamOS', '\\EFI\\steamos\\steamcl.efi')
    assert steamos.resolve([real, plain], esp=None) == plain


def test_a_healthy_install_has_two_entries_on_one_partition():
    proper = entry(3, 'SteamOS', '\\EFI\\steamos\\steamcl.efi', partition=ESP)
    fallback = entry(0x0C, 'UEFI OS', '\\EFI\\BOOT\\BOOTX64.EFI',
                     partition=ESP)
    assert steamos.resolve([fallback, proper], esp=ESP) == proper


def test_the_partition_still_outranks_a_loader_on_another_disk():
    fallback = entry(0x0C, 'UEFI OS', '\\EFI\\BOOT\\BOOTX64.EFI',
                     partition=ESP)
    stale = clone(2, partition='dead0000-0000-0000-0000-000000000001')
    assert steamos.score(fallback, esp=ESP) > steamos.score(stale, esp=ESP)
    assert steamos.resolve([stale, fallback], esp=ESP) == fallback


def test_a_visible_entry_wins_a_tie_against_a_hidden_one():
    hidden = entry(2, 'SteamOS', '\\EFI\\steamos\\steamcl.efi',
                   attributes=0x0009)
    visible = entry(5, 'SteamOS', '\\EFI\\steamos\\steamcl.efi',
                    attributes=0x0001)
    assert hidden.hidden and not visible.hidden
    assert steamos.resolve([hidden, visible]) == visible


def test_a_hidden_entry_is_still_the_answer_when_it_is_the_only_one():
    hidden = entry(2, 'SteamOS', '\\EFI\\steamos\\steamcl.efi',
                   attributes=0x0009)
    assert steamos.resolve([hidden]) == hidden


def test_hidden_never_outranks_the_partition_table():
    real = entry(0x0C, 'UEFI OS', '\\EFI\\BOOT\\BOOTX64.EFI',
                 partition=ESP, attributes=0x0009)
    decoy = clone(2, partition='dead0000-0000-0000-0000-000000000001')
    assert steamos.resolve([decoy, real], esp=ESP) == real
