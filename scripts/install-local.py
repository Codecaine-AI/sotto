#!/usr/bin/env python3
"""Build, verify, replace, and reopen the consistently signed local V07 app."""
import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path('/Applications/V07.app')
CONFIG = Path.home() / '.config/sotto/signing.json'
BUNDLE_ID = 'dev.davis.v07'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def requirement(app):
    result = subprocess.run(['codesign', '-d', '-r-', str(app)], check=True, capture_output=True, text=True)
    return next(line.removeprefix('# ') for line in (result.stdout + result.stderr).splitlines()
                if line.removeprefix('# ').startswith('designated =>'))


def installed_pids():
    result = subprocess.check_output(['ps', '-axo', 'pid=,comm='], text=True)
    executable = str(TARGET / 'Contents/MacOS/V07')
    return [int(parts[0]) for line in result.splitlines() if len(parts := line.strip().split(None, 1)) == 2 and parts[1] == executable]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adopt-identity', action='store_true',
                        help='Allow the one-time switch from the installed identity; permissions need reapproval.')
    args = parser.parse_args()
    if not CONFIG.is_file():
        raise SystemExit('Run python3 scripts/setup-local-signing.py first. No app was changed.')
    config = json.loads(CONFIG.read_text())
    identity = config.get('identity', '')
    if not re.fullmatch('[0-9a-fA-F]{40}', identity):
        raise SystemExit('Invalid signing configuration. No app was changed.')
    ROOT.joinpath('.local').mkdir(exist_ok=True)
    with ROOT.joinpath('.local/install.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another local install is running.')
        environment = dict(os.environ)
        # This command always uses the pinned local certificate.
        environment.pop('V07_SIGNING_IDENTITY', None)
        run(str(ROOT / 'scripts/build-app.sh'), cwd=ROOT, env=environment)
        built = ROOT / 'build/V07.app'
        expected = f'=identifier "{BUNDLE_ID}" and certificate leaf = H"{identity}"'
        run('codesign', '--verify', '--strict', '-R', expected, str(built))
        new_requirement = requirement(built)
        if TARGET.is_symlink():
            raise SystemExit('The install target is a symlink. No installed app was changed.')
        if TARGET.exists():
            with TARGET.joinpath('Contents/Info.plist').open('rb') as file:
                if plistlib.load(file).get('CFBundleIdentifier') != BUNDLE_ID:
                    raise SystemExit('A different app occupies the install path.')
            old_requirement = requirement(TARGET)
            if old_requirement != new_requirement and not args.adopt_identity:
                raise SystemExit('The signing identity would change. Use --adopt-identity only for an intentional one-time switch.')
        stage = Path(tempfile.mkdtemp(prefix='.V07-install-', dir=TARGET.parent))
        previous = None
        try:
            staged_app = stage / TARGET.name
            run('ditto', str(built), str(staged_app))
            run('codesign', '--verify', '--deep', '--strict', '-R', expected, str(staged_app))
            for pid in installed_pids():
                try:
                    os.kill(pid, 15)
                except ProcessLookupError:
                    pass
            for _ in range(100):
                if not installed_pids():
                    break
                time.sleep(0.1)
            else:
                raise SystemExit('V07 did not quit. No app was replaced.')
            if TARGET.exists():
                backup = ROOT / '.local/install-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
                backup.mkdir(parents=True)
                previous = backup / TARGET.name
                TARGET.rename(previous)
            try:
                staged_app.rename(TARGET)
            except OSError:
                if previous:
                    previous.rename(TARGET)
                raise
            run('open', str(TARGET))
            for _ in range(50):
                if installed_pids():
                    break
                time.sleep(0.1)
            else:
                raise SystemExit(f'App installed but launch was not confirmed. Previous app: {previous}')
            print('Installed and opened:', TARGET)
            print('Stable signing identity:', identity)
            if previous:
                print('Rollback copy:', previous)
            print('No macOS permissions were reset.')
        finally:
            shutil.rmtree(stage)


if __name__ == '__main__':
    main()
