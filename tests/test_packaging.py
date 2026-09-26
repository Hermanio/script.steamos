# SPDX-License-Identifier: GPL-3.0-or-later
import os
import re
import shutil
import subprocess
import sys
import zipfile

import pytest

from .conftest import ADDON_DIR

pytestmark = pytest.mark.compliance

ADDON_ID = 'script.steamos'
SHIPPED = {'addon.py', 'addon.xml', 'LICENSE.txt', 'resources'}


@pytest.fixture(scope='module')
def extracted(tmp_path_factory):
    out_dir = str(tmp_path_factory.mktemp('dist'))
    subprocess.run([os.path.join(ADDON_DIR, 'package.sh'), out_dir],
                   check=True, capture_output=True, cwd=ADDON_DIR)
    zip_path = os.path.join(out_dir, os.listdir(out_dir)[0])
    target = str(tmp_path_factory.mktemp('extracted'))
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(target)
    assert os.listdir(target) == [ADDON_ID]
    return os.path.join(target, ADDON_ID)


def test_the_zip_holds_the_add_on_and_nothing_else(extracted):
    assert set(os.listdir(extracted)) == SHIPPED
    for dirpath, dirnames, filenames in os.walk(extracted):
        assert '__pycache__' not in dirnames, dirpath


def test_the_installed_add_on_runs_without_the_repository(extracted):
    result = subprocess.run(
        [sys.executable, '-B', '-c',
         'import sys; sys.path[:0] = [%r, %r]; import addon'
         % (os.path.join(ADDON_DIR, 'tests', 'stubs'), extracted)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_kodi_addon_checker_is_clean(extracted):
    checker = shutil.which('kodi-addon-checker') or \
        os.path.join(sys.prefix, 'bin', 'kodi-addon-checker')
    result = subprocess.run([checker, '--branch=omega', extracted],
                            capture_output=True, text=True)
    output = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout + result.stderr)
    problems = [line for line in output.splitlines()
                if line.startswith(('ERROR:', 'WARN:'))
                and not line.startswith('WARN: We found no problems')]
    assert not problems, '\n'.join(problems)
