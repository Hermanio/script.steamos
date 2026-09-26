# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
from . import efivars, esp, kodiutils as ku, steamos
from .constants import EFIVARS_DIR, PROBLEM_NOT_UEFI, PROBLEM_NO_EFIVARS


def run(firmware=None):
    firmware = firmware or efivars.Firmware()

    problem = firmware.problem()
    if problem:
        return fail('unusable firmware: %s' % problem,
                    problem_message(problem))

    try:
        entries = firmware.boot_entries()
    except efivars.EfiError as exc:
        return fail('reading boot entries failed: %s' % exc,
                    ku.localize(30204, 'Could not read the boot entries: %s')
                    % exc)

    if not entries:
        return fail('the firmware lists no boot entries',
                    ku.localize(30203, 'The firmware lists no boot entries.'))

    disks = esp.describe_partitions(firmware.partlabels, firmware.partitions)
    partitions = firmware.present_partitions()
    current = firmware.boot_current()
    steamos_esp = esp.steamos_partition(firmware.partlabels,
                                        firmware.partitions)

    target = steamos.resolve(entries, exclude=current, partitions=partitions,
                             esp=steamos_esp)
    if target is None:
        target = ask(entries, current, partitions, steamos_esp, disks)
    if target is None:
        return

    try:
        firmware.set_boot_next(target.number)
    except efivars.EfiError as exc:
        return fail('setting BootNext failed: %s' % exc,
                    ku.localize(30205, 'Could not set the next boot entry: %s')
                    % exc)

    if firmware.boot_next() != target.number:
        return fail('BootNext did not stick',
                    ku.localize(30206, 'The firmware did not keep the next '
                                       'boot entry.'))

    ku.log('BootNext set to %s (%s)' % (target.name, target.description))
    ku.reboot()


def ask(entries, current, partitions, steamos_esp, disks):
    ranked = steamos.candidates(entries, exclude=current, esp=steamos_esp)
    rest = [entry for entry in entries
            if entry not in ranked and not entry.application
            and entry.number != current]
    offered = sorted(ranked + rest,
                     key=lambda entry: (steamos.is_stale(entry, partitions),
                                        not entry.active,
                                        entry.hidden))

    if not offered:
        ku.error('nothing on this machine can be booted into')
        ku.ok(ku.localize(30208, 'Nothing here looks like SteamOS. None of '
                                 'the %d boot entries loads steamcl.efi or '
                                 'is named like SteamOS.') % len(entries))
        return None

    ku.log('asking between %d entries' % len(offered))
    chosen = ku.select(ku.localize(30005, 'Which one is SteamOS?'),
                       [describe(entry, partitions, disks)
                        for entry in offered])
    return None if chosen is None else offered[chosen]


def describe(entry, partitions, disks):
    row = '%04X   %s' % (entry.number, entry.description or entry.name)
    disk = disks.get(entry.partition) if entry.partition else None
    if disk:
        row += '   %s' % disk
    if steamos.is_stale(entry, partitions):
        row += '   [%s]' % ku.localize(30010, 'partition not visible')
    if not entry.active:
        row += '   [%s]' % ku.localize(30011, 'inactive')
    return row


def fail(logged, message):
    ku.error(logged)
    ku.ok(message)


def problem_message(problem):
    if problem == PROBLEM_NOT_UEFI:
        return ku.localize(30200, 'This machine did not start through UEFI, '
                                  'so its firmware has no boot menu to point '
                                  'at SteamOS.')
    if problem == PROBLEM_NO_EFIVARS:
        return ku.localize(30201, 'The kernel is not exposing EFI variables '
                                  'at %s.') % EFIVARS_DIR
    return ku.localize(30202, 'EFI variables cannot be written here. Changing '
                              'the next boot needs root, which Kodi has on '
                              'LibreELEC and usually does not on a desktop '
                              'Linux.')
