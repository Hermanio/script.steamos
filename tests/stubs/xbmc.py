# SPDX-License-Identifier: GPL-3.0-or-later
LOGDEBUG = 0
LOGINFO = 1
LOGWARNING = 2
LOGERROR = 3
LOGFATAL = 4

LOG = []
BUILTINS = []


def log(message, level=LOGINFO):
    LOG.append((level, message))


def executebuiltin(command, wait=False):
    BUILTINS.append(command)


def translatePath(path):
    return path


def sleep(_milliseconds):
    return None


def getCondVisibility(_condition):
    return False


def reset():
    del LOG[:]
    del BUILTINS[:]
