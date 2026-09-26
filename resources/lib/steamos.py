# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
from .constants import STEAMOS_LOADER, STEAMOS_NAME, STEAMOS_PATH_MARKER

SCORE_ESP = 10
SCORE_LOADER = 3
SCORE_PATH = 2
SCORE_DESCRIPTION = 1


def score(entry, esp=None):
    points = SCORE_ESP if esp and entry.partition == esp else 0
    loader = (entry.loader or '').replace('\\', '/').lower()
    if loader.rsplit('/', 1)[-1] == STEAMOS_LOADER:
        return points + SCORE_LOADER
    if STEAMOS_PATH_MARKER in loader:
        return points + SCORE_PATH
    if STEAMOS_NAME in (entry.description or '').lower():
        return points + SCORE_DESCRIPTION
    return points


def is_stale(entry, partitions):
    if partitions is None or not entry.partition:
        return False
    return entry.partition not in partitions


def looks_the_same(one, other):
    return (one.description, one.loader) == (other.description, other.loader)


def candidates(entries, exclude=None, esp=None):
    ranked = [(score(entry, esp), index, entry)
              for index, entry in enumerate(entries)
              if entry.number != exclude and entry.bootable]
    ranked = [item for item in ranked if item[0]]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _score, _index, entry in ranked]


def resolve(entries, exclude=None, partitions=None, esp=None):
    ranked = candidates(entries, exclude, esp)
    if not ranked:
        return None

    best = score(ranked[0], esp)
    tied = [entry for entry in ranked if score(entry, esp) == best]
    live = [entry for entry in tied if not is_stale(entry, partitions)]
    if not live:
        return None
    visible = [entry for entry in live if not entry.hidden]
    if visible:
        live = visible
    if len(live) == 1:
        return live[0]
    if all(looks_the_same(live[0], entry) for entry in live):
        return live[0]
    return None
