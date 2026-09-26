# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from resources.lib import esp


@pytest.fixture
def udev(tmp_path):
    def build(partitions):
        uuids = tmp_path / 'by-partuuid'
        labels = tmp_path / 'by-partlabel'
        devices = tmp_path / 'dev'
        for directory in (uuids, labels, devices):
            directory.mkdir(exist_ok=True)
        for index, (label, guid) in enumerate(partitions.items()):
            node = devices / ('sda%d' % index)
            node.write_text('')
            (uuids / guid).symlink_to(node)
            (labels / label).symlink_to(node)
        return str(labels), str(uuids)

    return build


STEAMOS_DISK = {
    'esp': 'e8ba5129-d543-4f4b-b523-af35b1264e1b',
    'efi-A': '3bd113e2-a85f-4263-8fa8-d0c2f16b72a0',
    'rootfs-A': '4bad8833-f15c-498c-aff6-c49e94b7b0f5',
    'home': 'a81518ec-777d-46a3-bce8-e7aea954a18d',
}


def test_a_steamos_disk_is_recognised_by_its_labels(udev):
    labels, uuids = udev(STEAMOS_DISK)
    assert esp.steamos_partition(labels, uuids) == STEAMOS_DISK['esp']


def test_an_esp_label_alone_is_not_enough(udev):
    labels, uuids = udev({'esp': 'aaaa0000-0000-0000-0000-000000000001',
                          'root': 'bbbb0000-0000-0000-0000-000000000002'})
    assert esp.steamos_partition(labels, uuids) is None


def test_a_steamos_disk_with_no_esp_label_is_not_guessed_at(udev):
    labels, uuids = udev({'rootfs-A': 'cccc0000-0000-0000-0000-000000000003'})
    assert esp.steamos_partition(labels, uuids) is None


def test_a_machine_udev_says_nothing_about_answers_none(tmp_path):
    missing = str(tmp_path / 'nothing')
    assert esp.steamos_partition(missing, missing) is None
    assert esp.labels(missing) is None
    assert esp.devices_by_guid(missing) is None


def test_the_guid_comes_back_lowercase(udev):
    labels, uuids = udev(STEAMOS_DISK)
    assert esp.steamos_partition(labels, uuids).islower()


def test_a_label_pointing_at_a_device_with_no_guid_is_not_invented(tmp_path):
    labels = tmp_path / 'by-partlabel'
    uuids = tmp_path / 'by-partuuid'
    labels.mkdir()
    uuids.mkdir()
    (labels / 'esp').symlink_to(tmp_path / 'ghost')
    (labels / 'rootfs-A').symlink_to(tmp_path / 'ghost')
    assert esp.steamos_partition(str(labels), str(uuids)) is None
