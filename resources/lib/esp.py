# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import os

from .constants import (PARTLABEL_DIR, PARTUUID_DIR, STEAMOS_ESP_LABEL,
                        STEAMOS_SLOT_LABELS)


def devices_by_guid(directory=PARTUUID_DIR):
    try:
        names = os.listdir(directory)
    except OSError:
        return None
    return {os.path.realpath(os.path.join(directory, name)): name.lower()
            for name in names}


def labels(directory=PARTLABEL_DIR):
    try:
        names = os.listdir(directory)
    except OSError:
        return None
    return {name: os.path.realpath(os.path.join(directory, name))
            for name in names}


def describe_partitions(partlabels=PARTLABEL_DIR, partuuids=PARTUUID_DIR):
    guids = devices_by_guid(partuuids) or {}
    named = {}
    for label, device in (labels(partlabels) or {}).items():
        named.setdefault(device, label)
    described = {}
    for device, guid in guids.items():
        label = named.get(device)
        described[guid] = ('%s (%s)' % (os.path.basename(device), label)
                           if label else os.path.basename(device))
    return described


def steamos_partition(partlabels=PARTLABEL_DIR, partuuids=PARTUUID_DIR):
    found = labels(partlabels)
    if not found:
        return None
    if not STEAMOS_SLOT_LABELS & set(found):
        return None
    device = found.get(STEAMOS_ESP_LABEL)
    if device is None:
        return None
    guids = devices_by_guid(partuuids)
    return (guids or {}).get(device)
