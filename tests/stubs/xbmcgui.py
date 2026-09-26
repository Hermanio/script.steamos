# SPDX-License-Identifier: GPL-3.0-or-later
OK_DIALOGS = []
SELECT_DIALOGS = []

SELECT_ANSWERS = []


class Dialog:
    def ok(self, heading, message):
        OK_DIALOGS.append((heading, message))
        return True

    def select(self, heading, options, **_kwargs):
        SELECT_DIALOGS.append((heading, list(options)))
        return SELECT_ANSWERS.pop(0) if SELECT_ANSWERS else -1


def reset():
    for recorder in (OK_DIALOGS, SELECT_DIALOGS, SELECT_ANSWERS):
        del recorder[:]
