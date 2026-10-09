#!/usr/bin/env python3
"""Transfer requests waiting for the user's answer.

Nothing arrives unasked. When a sender asks to send, airdrop-serve.py holds
the /Ask open, as an Apple receiver does while its prompt is on screen, and
records the request here as <id>.json. `omdrop accept|decline` answers it by
writing <id>.answer beside it; the receiver reads that, replies to the sender,
and removes both. The directory is under XDG_RUNTIME_DIR, so only this user
can answer, and a reboot leaves nothing behind.

Everything in a request -- the sender's name, the file names, the sizes -- is
the sender's own claim. It is cleaned here for display and nothing more.

Both files are written whole and renamed into place, so a reader never sees
half of one. This module is the only thing that knows their format: the
receiver imports it, and `omdrop` runs it.
"""
import html
import json
import os
import re
import secrets
import sys
import time

ASK_DIR = os.path.join(os.environ.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}',
                       'omdrop', 'asks')
ID_RE = re.compile(r'^[0-9a-f]{16}$')
VERDICTS = ('accept', 'decline')

# Control and format characters, the last because a bidi override can make a
# name read as something it is not; file names also lose path separators, as
# the receiver's own file names do.
UNSAFE_CHAR = re.compile(r'[\x00-\x1f\x7f-\x9f]|[\u202a-\u202e\u2066-\u2069\u200b-\u200f\ufeff]')
PATH_CHAR = re.compile(r'[/\\]')


def clean(value, limit, path=False):
    text = UNSAFE_CHAR.sub('', value if isinstance(value, str) else '')
    return (PATH_CHAR.sub('', text) if path else text)[:limit].strip()


def summarize(ask, limit):
    """Who is asking and what they want to send, from an /Ask's plist."""
    files = []
    for f in (ask.get('Files') or [])[:limit]:
        if not isinstance(f, dict):
            continue
        size = f.get('FileSize')
        files.append({'name': clean(f.get('FileName'), 255, path=True) or 'a file',
                      'size': size if isinstance(size, int) and size >= 0 else None})
    links = []
    if 'links' in (ask.get('TransferType') or {}):
        links = [item[:2048] for item in (ask.get('Items') or [])[:limit]
                 if isinstance(item, str) and item.startswith(('http://', 'https://'))]
    return {'sender': clean(ask.get('SenderComputerName'), 63) or 'An unnamed device',
            'model': clean(ask.get('SenderModelName'), 63),
            'files': files, 'links': links}


def _write(path, data):
    tmp = os.path.join(os.path.dirname(path), f'.{os.path.basename(path)}.{secrets.token_hex(4)}')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _paths(ask_id):
    return os.path.join(ASK_DIR, f'{ask_id}.json'), os.path.join(ASK_DIR, f'{ask_id}.answer')


# ----------------------------------------------------------------- receiver

def prepare():
    """Create the directory and drop anything a previous receiver left."""
    os.makedirs(ASK_DIR, mode=0o700, exist_ok=True)
    clear()


def clear():
    try:
        names = os.listdir(ASK_DIR)
    except OSError:
        return
    for name in names:
        try:
            os.unlink(os.path.join(ASK_DIR, name))
        except OSError:
            pass


def publish(summary, seconds):
    """Record a request; returns its id. Raises OSError if it cannot."""
    ask_id = secrets.token_hex(8)
    record = dict(summary, id=ask_id, expires=time.time() + seconds)
    _write(_paths(ask_id)[0], json.dumps(record))
    return ask_id


def verdict(ask_id):
    """'accept', 'decline', or None while unanswered."""
    try:
        with open(_paths(ask_id)[1]) as fh:
            said = fh.read().strip()
    except FileNotFoundError:
        return None
    return said if said in VERDICTS else None


def withdraw(ask_id):
    for path in _paths(ask_id):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


# ----------------------------------------------------------------- omdrop

def pending():
    """The requests still waiting, oldest first, each with expires_in."""
    now = time.time()
    out = []
    try:
        names = sorted(os.listdir(ASK_DIR))
    except OSError:
        return out
    for name in names:
        if not name.endswith('.json') or not ID_RE.match(name[:-5]):
            continue
        try:
            with open(os.path.join(ASK_DIR, name)) as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            continue
        left = int(record.get('expires', 0) - now)
        if left <= 0:
            continue
        record['expires_in'] = left
        record['summary'] = describe(record)
        out.append(record)
    out.sort(key=lambda r: r['expires'])
    return out


def human_size(n):
    for unit in ('bytes', 'KB', 'MB', 'GB'):
        if n < 1000 or unit == 'GB':
            return f'{n} {unit}' if unit == 'bytes' else f'{n:.1f} {unit}'.replace('.0 ', ' ')
        n /= 1000


def describe(record):
    """'photo.jpg (2.1 MB)', 'photo.jpg and 2 more (12 MB)', or the link."""
    files, links = record.get('files') or [], record.get('links') or []
    if links and not files:
        return links[0] if len(links) == 1 else f'{links[0]} and {len(links) - 1} more links'
    if not files:
        return 'something'
    sizes = [f['size'] for f in files if f.get('size') is not None]
    total = f' ({human_size(sum(sizes))})' if len(sizes) == len(files) else ''
    first = files[0]['name']
    if len(files) == 1:
        return f'{first}{total}'
    return f'{first} and {len(files) - 1} more{total}'


def answer(ask_id, said):
    """Write the user's answer. False if the request is no longer waiting."""
    request, reply = _paths(ask_id)
    if not ID_RE.match(ask_id) or said not in VERDICTS or not os.path.exists(request):
        return False
    _write(reply, said + '\n')
    return True


def main(argv):
    cmd = argv[0] if argv else ''
    if cmd == 'json':
        print(json.dumps(pending()))
    elif cmd == 'dir':
        print(ASK_DIR)
    elif cmd == 'ids':
        for record in pending():
            print(record['id'])
    elif cmd == 'text':
        for record in pending():
            print(f"{record['sender']} wants to send {record['summary']}  "
                  f"[omdrop accept|decline {record['id']}, {record['expires_in']}s left]")
    elif cmd == 'toast' and len(argv) == 2:
        # Three lines for the notification: the sender (`omdrop` makes the
        # plain-text headline of it), the body (the shell renders it as
        # markup, so escaped), and seconds left.
        for record in pending():
            if record['id'] == argv[1]:
                print(record['sender'])
                print(html.escape(f"{record['summary']}. Click to accept or decline.", quote=False))
                print(record['expires_in'])
                return 0
        return 1
    elif cmd == 'answer' and len(argv) == 3:
        return 0 if answer(argv[1], argv[2]) else 1
    else:
        print('usage: asks.py json | dir | ids | text | toast ID | answer ID accept|decline',
              file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
