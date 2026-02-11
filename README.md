# XChat (Tor-style instant messenger)

XChat is a lightweight Python 3 instant messenger inspired by TorChat.
It uses Tor hidden services for incoming connections and Tor SOCKS for outgoing
peer-to-peer chat messages.

## Features

- Tor onion identity generated at startup (ephemeral hidden service).
- P2P text chat using `.onion` addresses.
- Classic split-pane UI inspired by old TorChat layouts.
- Debian packaging metadata and a helper script to build `.deb` files.

## Requirements

- Python 3.9+
- Tor daemon with:
  - `SocksPort` enabled (default `9050`)
  - `ControlPort` enabled (default `9051`)
  - Authentication configured (`CookieAuthentication 1` is enough on most systems)

Install runtime dependencies:

```bash
python3 -m pip install -e .
```

## Run

```bash
xchat
```

Environment overrides:

- `XCHAT_TOR_SOCKS_HOST` / `XCHAT_TOR_SOCKS_PORT`
- `XCHAT_TOR_CONTROL_HOST` / `XCHAT_TOR_CONTROL_PORT`
- `XCHAT_TOR_CONTROL_PASSWORD`
- `XCHAT_TOR_VIRTUAL_PORT`

## Build Debian package

Use the helper script (similar to TorChat-style packaging workflow):

```bash
./scripts/build_deb.sh
```

This runs `dpkg-buildpackage` and outputs a `.deb` in the parent directory.
