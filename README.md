# Boot into SteamOS

**A Kodi add-on that restarts the machine into SteamOS, for one boot.**

> **Unofficial.** Not affiliated with, endorsed by or supported by Valve
> Corporation. Steam and SteamOS are trademarks of Valve Corporation. The
> artwork is an original drawing, not Valve's.

On a box that dual-boots LibreELEC and SteamOS, getting to SteamOS normally
means a keyboard and the firmware's boot menu. This add-on is a button you
can press with a remote instead: launch it and the machine reboots into
SteamOS. Shut SteamOS down and the next boot is LibreELEC again.

## How it works

It sets UEFI `BootNext` to the SteamOS entry and reboots. It does this
through efivarfs in plain Python, because neither LibreELEC nor SteamOS
ships `efibootmgr`.

1. **Preflight.** `/sys/firmware/efi` must exist and efivars must be
   writable, which means Kodi runs as root. Otherwise it shows a dialog
   saying which check failed.
2. **Parse.** Each `Boot####` is read as an `EFI_LOAD_OPTION`: description,
   attributes (active, hidden, app category) and device path. The device
   path gives the GPT partition GUID and the loader path. `BootOrder` and
   `BootCurrent` are read too.
3. **Rank.** Each entry is scored:
   - +10 if it sits on SteamOS's ESP, found through udev `by-partlabel`
     (`esp` plus an `efi-A`/`rootfs-A` slot label) mapped to `by-partuuid`
   - +3 if its loader is `steamcl.efi`
   - +2 if its path contains `steamos`
   - +1 if its description matches

   The running system (`BootCurrent`), inactive and firmware-app entries,
   and entries whose partition is gone from `by-partuuid` are dropped.
   Among the top scorers, a visible entry beats a hidden one, and identical
   duplicates resolve to the first in `BootOrder`. Anything still ambiguous
   is shown as a list giving each entry's number, description and disk.
4. **Arm.** It clears the efivarfs immutable flag, writes
   `BootNext` (attributes NV|BS|RT plus the entry number), and reads it back.
   If the firmware dropped it, the add-on reports that instead of rebooting.
5. **Reboot.** The firmware consumes `BootNext`, so the boot after SteamOS
   falls back to `BootOrder`, which is LibreELEC.

No settings and nothing remembered between runs.

## Requirements

- Kodi 21 (Omega) or newer, on Linux.
- A machine booted through **UEFI** with `/sys/firmware/efi/efivars`.
- Kodi running as **root**, as it does on LibreELEC. A desktop Kodi running
  as a normal user cannot write boot variables, and the add-on says so.

## Installing

1. Download `script.steamos-<version>.zip` from the
   [latest release](https://github.com/Hermanio/script.steamos/releases/latest).
2. In Kodi, enable **Settings → System → Add-ons → Unknown sources**.
3. **Add-ons → Install from zip file**, pick the zip. It appears under
   **Program add-ons**.

There are no automatic updates. To update, install a newer zip the same
way; Kodi replaces the old version.

To put it on the home screen, add it to favourites from the context menu
and add that favourite to a home menu item in the skin's settings.

## Safety

Only `BootNext` is ever written; `BootOrder`, `Boot####` and every other
variable are read-only, and a test enforces it. A wrong pick costs one
reboot, and the boot after it is normal again. Cancelling the list changes
nothing. If your firmware ignores `BootNext`, the machine simply boots its
default system; use the firmware's own boot menu if it ever misbehaves.

Run `sudo ./run-tests.sh firmware` on the machine first to see every boot
entry and which one the add-on would pick, without writing anything.

## Tested on

| | |
|---|---|
| Board | Gigabyte B560M DS3H, Intel Core i5-10500 |
| Firmware | AMI F11 (2023-12-19), UEFI, Secure Boot off |
| LibreELEC | 12.2.1, kernel 6.16.12 x86_64 |
| Kodi | 21.3 (Omega) |

`BootNext` handling varies by firmware, so the firmware line is the one to
compare against your own.

## Reporting a problem

Open an issue at <https://github.com/Hermanio/script.steamos/issues>. Say
what happened (an error dialog, the list appeared, the wrong entry was
picked, or it rebooted somewhere other than SteamOS) and paste the output of
this, run as root on the Kodi machine (over SSH on LibreELEC):

```sh
{
d=/sys/class/dmi/id; v=/sys/firmware/efi/efivars; g=8be4df61-93ca-11d2-aa0d-00e098032b8c
echo "machine:     $(cat $d/sys_vendor $d/product_name | tr '\n' ' ')"
echo "firmware:    $(cat $d/bios_vendor $d/bios_version $d/bios_date | tr '\n' ' ')"
echo "os:          $(. /etc/os-release; echo "$NAME $VERSION"), kernel $(uname -r)"
echo "secure boot: $(tail -c1 $v/SecureBoot-$g | od -An -tu1 | tr -d ' ')"
grep -m1 'Starting Kodi' ~/.kodi/temp/kodi.log
grep 'script.steamos' ~/.kodi/temp/kodi.log | tail -20
for f in $v/Boot*-$g; do n=${f##*/}; echo "${n%%-*} $(base64 < $f | tr -d '\n')"; done
ls -l /dev/disk/by-partlabel /dev/disk/by-partuuid
} 2>&1
```

It prints the machine and firmware, the add-on's log lines, the raw boot
variables and the disk partitions. None of it is secret, but if anything
looks private to you (a hostname, a MAC address in a network boot entry),
remove it before posting.
The boot variable lines are what lets your machine be reproduced as a test
(`tools/record_fixtures.py --from`).

## Development

```bash
./run-tests.sh             # static + unit tests (~1s)
./run-tests.sh firmware    # this machine's real UEFI variables (root)
./run-tests.sh check       # build the zip and run kodi-addon-checker
./package.sh               # build dist/script.steamos-<version>.zip
python tools/record_fixtures.py --name mybox   # record a machine's variables
```

The tests run against a fabricated efivarfs in a temporary directory and
against boot variables recorded from real machines in `tests/fixtures/`.

To release, bump `version` and `<news>` in `addon.xml`, then push a tag
`v<version>`. GitHub Actions runs the tests, builds the zip and publishes it
as a release.

This add-on was written with the help of LLM-based coding tools and checked
against real hardware.

## Licence

GPL-3.0-or-later. See [LICENSE.txt](LICENSE.txt).
