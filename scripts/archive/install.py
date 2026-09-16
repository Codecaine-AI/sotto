#!/usr/bin/env python3
"""Configure the transcript archive worker for the current login session."""
import argparse
import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
from archive import atomic, encode


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--launcher-output')
    args=parser.parse_args()
    os.umask(0o077)
    repo=Path(__file__).resolve().parents[2]
    root=Path(args.root).expanduser().resolve()
    if not (root/'dataset.json').is_file():
        raise SystemExit('The archive must exist before installation.')
    config={'archive_root':str(root),'sotto_data':str(repo/'.local/server'),'viewer_url':'http://127.0.0.1:8392'}
    atomic(repo/'.local/archive-config.json',encode(config))
    label='ai.codecaine.sotto.archive'
    plist={'Label':label,'ProgramArguments':[sys.executable,str(repo/'scripts/archive/archive.py'),
        '--root',str(root),'--cache',str(repo/'.local/archive-cache'),'serve','--sotto-data',str(repo/'.local/server')],
        'WorkingDirectory':str(repo),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':15,
        'StandardOutPath':str(repo/'.local/archive-service.log'),'StandardErrorPath':str(repo/'.local/archive-service.log'),
        'Umask':0o077}
    path=repo/'.local'/f'{label}.plist'
    atomic(path,plistlib.dumps(plist))
    domain=f'gui/{os.getuid()}'
    service=f'{domain}/{label}'
    if subprocess.run(['launchctl','print',service],capture_output=True).returncode==0:
        subprocess.run(['launchctl','bootout',service],check=True)
    subprocess.run(['launchctl','bootstrap',domain,str(path)],check=True)
    launcher='''#!/bin/bash
set -euo pipefail
sotto_root=ROOT
sotto_domain="gui/$(id -u)"
for sotto_label in ai.codecaine.sotto.server ai.codecaine.sotto.archive; do
    if ! launchctl print "$sotto_domain/$sotto_label" >/dev/null 2>&1; then
        launchctl bootstrap "$sotto_domain" "$sotto_root/.local/$sotto_label.plist"
    fi
    launchctl kickstart "$sotto_domain/$sotto_label"
done
open /Applications/Sotto.app
printf 'Sotto is open. The Data page shows your shared transcript archive.\\n'
'''.replace('ROOT',shlex.quote(str(repo)),1)
    destinations=[repo/'.local/Start Sotto.command']
    if args.launcher_output:destinations.append(Path(args.launcher_output).expanduser())
    for p in destinations:
        atomic(p,launcher.encode());p.chmod(0o755)
    print('Archive service configured for this login session:',root)

if __name__=='__main__':main()
