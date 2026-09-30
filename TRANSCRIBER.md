# Transcriber

Transcriber is Codecaine's build of this project. It follows the upstream source and installs under its own fixed name, so an upstream rename never changes what macOS sees.

| What                  | Value                                       |
| --------------------- | ------------------------------------------- |
| Installed app         | `/Applications/Transcriber.app`             |
| Bundle identifier     | `ai.codecaine.transcriber`                  |
| Client settings       | `~/Library/Application Support/Transcriber` |
| Keychain service      | `ai.codecaine.transcriber.server`           |
| Signing configuration | `~/.config/transcriber/signing.json`        |

macOS ties Microphone, Accessibility, and Input Monitoring grants to the bundle identifier and the signing certificate. Both stay the same across rebuilds and upstream syncs, so the grants persist.

## How the name is applied

`scripts/install-local.py` runs upstream's `scripts/build-app.sh` unchanged. It then copies the result to `build/Transcriber.app`, rewrites the name and identifier in the copy's `Info.plist`, and signs the copy with the pinned local certificate. The app reads its name and identifier from its own bundle (`V07Build.swift`), so the settings directory and Keychain service follow the bundle.

Upstream's source tree, module names, `README.md`, and build scripts keep upstream's names. That keeps syncs free of rename conflicts. A few fixed labels inside the app window still show upstream's name.

## Commands

```sh
python3 scripts/setup-local-signing.py        # Once per Mac: create the signing certificate
./scripts/rebuild-local.sh --build-only       # Build and sign build/Transcriber.app
./scripts/rebuild-local.sh                    # Build, back up the installed app, replace it, reopen it
```

Project documentation lives in the [Docs corpus](docs/00-foundation/doc.json); start with [Current Status](docs/00-foundation/20-current-status/doc.json). The transcript archive is described in [scripts/archive/README.md](scripts/archive/README.md).
