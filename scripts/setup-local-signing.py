#!/usr/bin/env python3
"""Create or reuse Transcriber's local code-signing identity in the login Keychain."""
import json
import os
from pathlib import Path
import re
import shutil
import secrets
import subprocess
import tempfile

NAME = 'Transcriber Local Development'
CONFIG = Path.home() / '.config/transcriber/signing.json'
KEYCHAIN = Path.home() / 'Library/Keychains/login.keychain-db'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    os.umask(0o077)
    if CONFIG.exists():
        saved = json.loads(CONFIG.read_text())
        print('Using the configured identity:', saved['identity'])
        return
    with tempfile.TemporaryDirectory(prefix='transcriber-signing-') as temporary:
        root = Path(temporary)
        cert = root / 'certificate.pem'
        existing = subprocess.run(['security', 'find-certificate', '-a', '-c', NAME, '-p', str(KEYCHAIN)],
                                  capture_output=True, text=True)
        if existing.returncode == 0 and existing.stdout.count('BEGIN CERTIFICATE') == 1:
            cert.write_text(existing.stdout)
            print('Reusing the existing Transcriber certificate.')
        elif existing.returncode == 0 and existing.stdout.count('BEGIN CERTIFICATE') > 1:
            raise SystemExit('Multiple Transcriber certificates exist. Select one explicitly; no identity was changed.')
        else:
            config = root / 'certificate.cnf'
            config.write_text('''[req]
prompt = no
distinguished_name = subject
x509_extensions = codesign
[subject]
CN = Transcriber Local Development
[codesign]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
subjectKeyIdentifier = hash
''')
            key = root / 'private-key.pem'
            run('/usr/bin/openssl', 'req', '-new', '-x509', '-newkey', 'rsa:3072', '-nodes',
                '-days', '3650', '-config', str(config), '-keyout', str(key), '-out', str(cert),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Non-extractable key; only codesign receives an explicit access entry.
            # No passwords or private keys are written to the project or config.
            identity_file = root / 'identity.p12'
            temporary_passphrase = secrets.token_hex(24)
            passfile = root / 'import-passphrase'
            passfile.write_text(temporary_passphrase)
            run('/usr/bin/openssl', 'pkcs12', '-export', '-in', str(cert), '-inkey', str(key),
                '-name', NAME, '-out', str(identity_file), '-passout', 'file:' + str(passfile),
                '-keypbe', 'PBE-SHA1-3DES', '-certpbe', 'PBE-SHA1-3DES', '-macalg', 'sha1')
            imported = subprocess.run(['security', 'import', str(identity_file), '-k', str(KEYCHAIN), '-f', 'pkcs12',
                '-P', temporary_passphrase, '-x', '-T', '/usr/bin/codesign'])
            if imported.returncode:
                raise SystemExit('Keychain import failed. No signing configuration was changed.')
        fingerprint = output('/usr/bin/openssl', 'x509', '-in', str(cert), '-noout', '-fingerprint', '-sha1').split('=')[-1].replace(':', '')
        if not re.fullmatch('[0-9A-Fa-f]{40}', fingerprint):
            raise SystemExit('Invalid signing fingerprint.')
        requirements = []
        for version in (1, 2):
            source = root / f'probe-{version}.c'
            binary = root / f'probe-{version}'
            source.write_text(f'int main(void) {{ return {version}; }}\n')
            run('xcrun', 'clang', str(source), '-o', str(binary))
            requirement = f'=designated => identifier "ai.codecaine.transcriber.signing-probe" and certificate leaf = H"{fingerprint}"'
            run('codesign', '--force', '--sign', fingerprint, '--keychain', str(KEYCHAIN),
                '--identifier', 'ai.codecaine.transcriber.signing-probe', '--requirements', requirement, str(binary))
            run('codesign', '--verify', '--strict', str(binary))
            detail = subprocess.run(['codesign', '-d', '-r-', str(binary)], check=True, capture_output=True, text=True)
            requirements.append(next(line for line in (detail.stdout + detail.stderr).splitlines() if line.startswith('designated =>')))
        if requirements[0] != requirements[1] or 'cdhash' in requirements[0]:
            raise SystemExit('Signing identity changed across probe builds. Configuration was not saved.')
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cert, CONFIG.parent / 'local-signing-certificate.pem')
        pending = CONFIG.with_suffix('.json.tmp')
        pending.write_text(json.dumps({'identity': fingerprint, 'keychain': str(KEYCHAIN),
                                       'name': NAME, 'pinCertificate': True}, indent=2) + '\n')
        pending.replace(CONFIG)
        print('Verified stable identity across two different binaries.')
        print('Saved public signing configuration:', CONFIG)
        print('The private key remains in the login Keychain.')


if __name__ == '__main__':
    main()
