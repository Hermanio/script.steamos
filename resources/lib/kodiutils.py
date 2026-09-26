# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')


def log(message, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, message), level)


def error(message):
    log(message, xbmc.LOGERROR)


def localize(string_id, default=''):
    return ADDON.getLocalizedString(string_id) or default


def ok(message, heading=None):
    xbmcgui.Dialog().ok(heading or ADDON_NAME, message)


def select(heading, rows):
    chosen = xbmcgui.Dialog().select(heading, rows)
    return None if chosen is None or chosen < 0 else chosen


def reboot():
    xbmc.executebuiltin('Reboot')
