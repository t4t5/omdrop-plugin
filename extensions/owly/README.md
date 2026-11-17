# Owly radio backend for other distributions

Omdrop's default radio backend is `omdrop-awdl`, for the Broadcom Wi-Fi in
Apple Silicon Macs. This extension lets the same panel, `omdrop` command and
receiver work on **other Linux distributions** with a Wi-Fi card that
[Owly](https://github.com/t4t5/owly) can drive: Intel, Realtek, MediaTek and
Atheros cards, including USB adapters.

The backend is a small set of helpers that make `awdl0` exist and announce
this machine on it. Omdrop finds them at fixed paths, or through
`OMDROP_DISCOVERABLE` and `OMDROP_SENDER`. See
[`docs/radio-backend.md`](../../docs/radio-backend.md) for the helper contract.

> **Why this matters for device lists:** Owly's receiver publishes a stable
> mDNS identity from `~/.local/state/owly/receiver-id` and sends a TTL-0
> goodbye when it stops ([issue #125](https://github.com/t4t5/owly/issues/125)).
> That fix landed after the 0.4.3 release, so until it ships in a release,
> build Owly from source or use a package built from a checkout that contains
> it. Older versions publish a fresh identity per run, and iPhones accumulate
> a new "this computer" entry for every restart.

## Requirements

- A Wi-Fi card listed as working in Owly's
  [supported hardware](https://github.com/t4t5/owly#supported-hardware).
  Check it first with `owly doctor`.
- **Owly** installed (CLI and `owlyd`), version 0.4.3 or newer.
- Rust 1.88 or newer, to build the backend helpers from source. There is no
  `omdrop-owl` binary package for Fedora or Debian yet; Arch users can install
  the `omdrop-owl` AUR package instead and skip the build.
- `sudo`, `git`, and a polkit agent for the root-owned radio helper.

## Install Owly

Install the release package for your distribution from
[Owly's releases page](https://github.com/t4t5/owly/releases):

```sh
# Fedora 44+
sudo dnf install ./owly-*.x86_64.rpm

# Debian 12 / Ubuntu 22.04+
sudo apt install ./owly_*_amd64.deb

# Arch / Omarchy
yay -S owly
```

Verify it before going further:

```sh
owly --version
sudo owly doctor
```

If your card is marked opt-in in the hardware table, allow it in
`/etc/owly/radio.toml`:

```toml
allow_untested = true
```

For a USB adapter used as a second card, point Owly at it and disconnect it
from NetworkManager:

```toml
station = "wlp0s20f0u3"
```

```sh
nmcli device disconnect wlp0s20f0u3
```

## Install the backend helpers

From a checkout of this plugin:

```sh
extensions/owly/install.sh
```

The script detects the distribution, checks that Owly is present, builds
`omdrop-owl` from a source checkout of Owly, and runs Owly's
`packaging/install.sh omdrop-owl` to install the helpers. It prompts before
using `sudo`.

Useful options:

```sh
extensions/owly/install.sh --source ~/src/owly   # use a local Owly checkout
extensions/owly/install.sh --tag v0.4.3           # build a specific release
extensions/owly/install.sh --dest /tmp/stage     # stage files, no sudo
extensions/owly/install.sh --skip-build          # reuse an existing target/release
extensions/owly/install.sh --check               # verify, change nothing
extensions/owly/install.sh --dry-run             # print the commands only
```

The install places:

| Path | What |
|---|---|
| `/usr/lib/omdrop/omdrop-discoverable` | root radio helper (run through pkexec) |
| `/usr/lib/omdrop/send-to-peer` | sender used by `omdrop send` and `omdrop peers` |
| `/usr/lib/omdrop/radio/{probe,up,tick,down,peers}` | omdrop-core hooks |
| `/usr/share/polkit-1/actions/io.github.t4t5.omdrop-owl.policy` | polkit rule |

If the helpers are staged elsewhere, point Omdrop at them explicitly:

```sh
export OMDROP_DISCOVERABLE=/path/to/stage/usr/lib/omdrop/omdrop-discoverable
export OMDROP_SENDER=/path/to/stage/usr/lib/omdrop/send-to-peer
```

Put those lines in your shell profile only for a non-standard install; the
default paths need no environment variables.

## Firewall

The receiver listens on TCP 8771 on `awdl0`. With ufw, let the plugin add the
rule:

```sh
omdrop firewall install
```

With firewalld, open the port for the `awdl0` zone (adjust the zone name to
the one `awdl0` is in):

```sh
sudo firewall-cmd --permanent --zone=nmmanaged --add-port=8771/tcp
sudo firewall-cmd --reload
firewall-cmd --get-zone-of-interface=awdl0
```

The rule should accept only IPv6 link-local sources; a wide-open TCP 8771 is
not necessary.

## Verify

```sh
owly doctor                              # the card and its mode
/usr/lib/omdrop/omdrop-discoverable probe --json
omdrop status
omdrop peers -n
```

Then click the Omdrop icon and turn receiving on. The iPhone's AirDrop share
sheet should list this computer once. Turning receiving off and on again
should keep **one** entry, not add another.

## Troubleshooting

- **`owly radio up` fails**: the card is unsupported or needs `allow_untested`
  in `/etc/owly/radio.toml`. Run `owly doctor` for the exact reason.
- **No tile on the iPhone**: check the firewall rule, that AirDrop is set to
  "Everyone for 10 minutes", and that the phone's screen is on. `owly doctor`
  reports which channel the radio uses; shared mode needs the AP on channel
  6, 44 or 149.
- **pkexec asks for a password every time**: a symlinked helper must resolve
  to its real path with the polkit rule matching it. The installer installs
  the wrapper at the real path; do not point `OMDROP_DISCOVERABLE` at a
  symlink in `~/.local/bin`.
- **Multiple "this computer" entries**: use Owly 0.4.3 or newer with the
  stable receiver ID, or delete the stale entries by toggling AirDrop off/on
  on the iPhone.
- **`omdrop install-driver` refuses to run**: that command installs the
  Broadcom driver and receiver packages. The owly backend is a separate
  package installed by this extension; update it by rerunning
  `extensions/owly/install.sh`.

## Uninstall

In an Owly source checkout, list what the backend installed:

```sh
packaging/install.sh --list omdrop-owl
```

Remove those paths (the helpers, the hooks, the polkit rule and the policy),
then `omarchy plugin remove netmojo.omdrop` if you no longer want the panel.
The Owly package itself can be removed with `sudo dnf remove owly` or
`sudo apt remove owly`.
