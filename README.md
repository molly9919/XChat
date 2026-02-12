# XChat (Tor-style instant messenger)

XChat is a lightweight Python 3 instant messenger inspired by TorChat.
It uses Tor hidden services for incoming connections and Tor SOCKS for outgoing
peer-to-peer chat messages.

## Features

- Persistent Tor ID (same onion each launch) with manual **Refresh ID** option when you want a new one.
- P2P text chat using `.onion` addresses.
- Classic split-pane UI inspired by old TorChat layouts.
- One-click copy for your own Tor ID and selected peer Tor IDs.
- Reliable peer ID input with Add button (auto-uses clipboard when field is empty), right-click menu, and Ctrl+V/Shift+Insert support.
- Saved peer list across restarts, with manual remove option (button or Delete key).
- Debian packaging metadata and a helper script to build `.deb` files.

## Requirements

- Python 3.9+
- Tor executable available on the system (`tor` package) **or** custom tor path via
  `XCHAT_TOR_BINARY`.

XChat starts and manages its own private Tor process by default (TorChat-style), so
no system Tor service needs to be running.

Install runtime dependencies:

```bash
python3 -m pip install -e .
```

## Run

```bash
xchat
```

When installed from the Debian package, the app is also available in the desktop
menu as **XChat (Tor Messenger)**.

Environment overrides:

- `XCHAT_PRIVATE_TOR` (`1`/`0`, default `1`)
- `XCHAT_TOR_BINARY`
- `XCHAT_TOR_DATA_DIR`
- `XCHAT_ONION_KEY_FILE` (where persistent onion private key is stored)
- `XCHAT_PEERS_FILE` (where saved peer list is stored)
- `XCHAT_TOR_SOCKS_HOST` / `XCHAT_TOR_SOCKS_PORT`
- `XCHAT_TOR_CONTROL_HOST` / `XCHAT_TOR_CONTROL_PORT`
- `XCHAT_TOR_CONTROL_PASSWORD`
- `XCHAT_TOR_VIRTUAL_PORT`

## Build Debian package

Use the helper script (similar to TorChat-style packaging workflow):

```bash
./scripts/build_deb.sh
```

If build dependencies are missing, install them automatically and build in one step:

```bash
./scripts/build_deb.sh --install-deps
```

This runs `dpkg-checkbuilddeps` first, then `dpkg-buildpackage`, and outputs a `.deb`
in the parent directory.
