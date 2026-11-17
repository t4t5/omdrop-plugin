#!/bin/sh
# Install Owly's radio backend helpers so Omdrop works on distributions
# without an omdrop-owl binary package. See README.md beside this script.
set -eu

usage() {
  cat <<EOF
usage: $(basename "$0") [options]

Install the omdrop-owl radio backend for Omdrop from an Owly source checkout.

  --source DIR     use a local Owly checkout instead of cloning a release
  --tag TAG        git tag/branch to clone (default: main)
  --dest DIR       staging root (DESTDIR), no sudo; for packaging and tests
  --skip-build     reuse an existing target/release build in the source tree
  --check          verify an installed backend, change nothing
  --dry-run        print the commands, change nothing
  --yes            do not ask before using sudo
  -h, --help       show this help
EOF
}

SOURCE=
TAG=main
DEST=
SKIP_BUILD=
CHECK=
DRY=
ASSUME_YES=
SUDO=

while [ $# -gt 0 ]; do
  case "$1" in
    --source)   [ $# -ge 2 ] || { echo "--source needs a directory" >&2; exit 2; }; SOURCE=$2; shift 2 ;;
    --tag)      [ $# -ge 2 ] || { echo "--tag needs a name" >&2; exit 2; }; TAG=$2; shift 2 ;;
    --dest)     [ $# -ge 2 ] || { echo "--dest needs a directory" >&2; exit 2; }; DEST=$2; shift 2 ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --check)    CHECK=1; shift ;;
    --dry-run)  DRY=1; shift ;;
    --yes)      ASSUME_YES=1; shift ;;
    -h|--help)  usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
run() {
  if [ -n "$DRY" ]; then
    printf 'DRY:'
    printf ' %s' "$@"
    printf '\n'
  else
    "$@"
  fi
}
need() {
  command -v "$1" >/dev/null 2>&1 || { say "missing command: $1"; exit 1; }
}
as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    need sudo
    if [ -z "$ASSUME_YES" ] && [ -z "$DRY" ]; then
      printf 'Install the backend helpers with sudo? [y/N] '
      read -r answer || exit 1
      case "$answer" in y|Y|yes|YES) ;; *) say 'aborted'; exit 1 ;; esac
    fi
    sudo "$@"
  fi
}

detect_os() {
  [ -f /etc/os-release ] || { say "/etc/os-release missing; use --source and --dest"; return; }
  # shellcheck disable=SC1091
  . /etc/os-release
  case "${ID:-}" in
    fedora|rhel|centos) say "Fedora/RHEL family: install Owly from an RPM release." ;;
    debian|ubuntu|linuxmint|pop) say "Debian family: install Owly from a .deb release." ;;
    arch|manjaro|endeavouros|cachyos) say "Arch family: 'yay -S owly omdrop-owl' already provides the backend." ;;
    *) say "Unknown distribution: install Owly from a release package." ;;
  esac
}

check_install() {
  root=${DEST:-}
  missing=
  for p in \
    usr/lib/omdrop/omdrop-discoverable \
    usr/lib/omdrop/send-to-peer \
    usr/lib/omdrop/awdl-airdrop-adv.py \
    usr/share/polkit-1/actions/io.github.t4t5.omdrop-owl.policy; do
    if [ ! -e "$root/$p" ]; then
      say "missing: $root/$p"
      missing=1
    fi
  done
  if [ -n "$missing" ]; then
    say "backend is not installed; run this script without --check"
    exit 1
  fi
  say "backend helpers present under ${root:-/}"
  exit 0
}

say "Owly backend extension for Omdrop"
[ -n "$CHECK" ] && check_install

detect_os
[ -n "$DRY" ] || need owly
owly --version >/dev/null 2>&1 || {
  say "owly is not on PATH. Install it from https://github.com/t4t5/owly/releases first."
  exit 1
}

WORK=
cleanup() { [ -n "$WORK" ] && [ -d "$WORK" ] && rm -rf "$WORK"; return 0; }
trap cleanup EXIT INT TERM

if [ -z "$SOURCE" ]; then
  need git
  WORK=$(mktemp -d "${TMPDIR:-/tmp}/owly-backend.XXXXXX")
  say "Cloning Owly ($TAG) into $WORK..."
  run git clone --depth 1 --branch "$TAG" https://github.com/t4t5/owly.git "$WORK/owly"
  SOURCE="$WORK/owly"
fi

if [ -z "$DRY" ]; then
  [ -d "$SOURCE" ] || { say "source directory not found: $SOURCE"; exit 1; }
  [ -x "$SOURCE/packaging/install.sh" ] || { say "not an Owly checkout: $SOURCE"; exit 1; }
fi

if [ -z "$SKIP_BUILD" ]; then
  [ -n "$DRY" ] || need cargo
  rustc --version 2>/dev/null || { say "rustc missing"; exit 1; }
  say "Building omdrop-owl in $SOURCE..."
  run sh -c "cd '$SOURCE' && cargo build --release --locked -p omdrop-owl"
fi

# On SELinux systems owlyd needs /usr/libexec, but this package installs no
# owlyd, so the default layout is fine everywhere; only DESTDIR is optional.
EXTRA=
[ -n "$DEST" ] && EXTRA="DESTDIR=$DEST"

if [ -n "$DRY" ]; then
  printf 'DRY: env %s %s/packaging/install.sh omdrop-owl\n' "$EXTRA" "$SOURCE"
else
  if [ -n "$DEST" ]; then
    DESTDIR=$DEST "$SOURCE/packaging/install.sh" omdrop-owl
  else
    as_root env "$SOURCE/packaging/install.sh" omdrop-owl
  fi
fi

say "Done. Verify with:"
say "  $SOURCE/packaging/install.sh --list omdrop-owl"
say "  /usr/lib/omdrop/omdrop-discoverable probe --json"
say "  omdrop status"
