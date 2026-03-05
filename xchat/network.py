from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import shutil
import socket
from subprocess import Popen
import threading
import time
from typing import Any

import socks
from stem import SocketError
from stem.control import Controller
from stem.process import launch_tor_with_config

from .config import TorConfig
from .protocol import decode_message, encode_message

MessageCallback = Callable[[str, str], None]
StatusCallback = Callable[[str], None]


def _pick_free_port(host: str = "127.0.0.1") -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind((host, 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class TorChatNode:
    HEARTBEAT_INTERVAL = 2.0
    PEER_TIMEOUT = 8.0

    def __init__(self, config: TorConfig, on_message: MessageCallback, on_status: StatusCallback):
        self.config = config
        self.on_message = on_message
        self.on_status = on_status
        self._listener: socket.socket | None = None
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._connections: dict[str, socket.socket] = {}
        self._conn_lock = threading.Lock()
        self._controller: Controller | None = None
        self._service: Any = None
        self._tor_process: Popen[bytes] | None = None
        self.own_onion: str | None = None

    def disconnect_peer(self, onion: str) -> None:
        address = onion.removesuffix(".onion") + ".onion"
        with self._conn_lock:
            conn = self._connections.pop(address, None)
        if conn is not None:
            conn.close()

    def restart_peer(self, onion: str) -> None:
        self.disconnect_peer(onion)
        self.connect_peer(onion)

    def start(self) -> None:
        if self.config.launch_private_tor:
            self._start_private_tor()
        self._start_listener()
        self._publish_onion_service(force_new=False)

    def stop(self) -> None:
        self._stop.set()
        if self._listener:
            self._listener.close()
        with self._conn_lock:
            for conn in self._connections.values():
                conn.close()
            self._connections.clear()
        if self._controller and self._service:
            self._controller.remove_ephemeral_hidden_service(self._service.service_id)
        if self._controller:
            self._controller.close()
        if self._tor_process:
            self._tor_process.terminate()
            self._tor_process.wait(timeout=10)

    def refresh_identity(self) -> str:
        if not self._listener:
            raise RuntimeError("Node is not started")
        self._publish_onion_service(force_new=True)
        if not self.own_onion:
            raise RuntimeError("Failed to refresh onion ID")
        return self.own_onion

    def _resolve_tor_binary(self) -> str:
        if self.config.tor_binary:
            return self.config.tor_binary

        bundled = Path(__file__).resolve().parent / "bin" / "tor"
        if bundled.exists() and bundled.is_file():
            return str(bundled)

        system_tor = shutil.which("tor")
        if system_tor:
            return system_tor

        raise RuntimeError(
            "Tor executable was not found. Install tor or set XCHAT_TOR_BINARY to a tor binary path."
        )

    def _start_private_tor(self) -> None:
        self.config.socks_port = self.config.socks_port or _pick_free_port(self.config.socks_host)
        self.config.control_port = self.config.control_port or _pick_free_port(self.config.control_host)

        data_dir = Path(self.config.tor_data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        tor_binary = self._resolve_tor_binary()
        self.on_status("Starting private Tor process…")

        self._tor_process = launch_tor_with_config(
            tor_cmd=tor_binary,
            config={
                "SocksPort": f"{self.config.socks_host}:{self.config.socks_port}",
                "ControlPort": f"{self.config.control_host}:{self.config.control_port}",
                "CookieAuthentication": "1",
                "DataDirectory": str(data_dir),
                "AvoidDiskWrites": "1",
            },
            take_ownership=True,
            completion_percent=100,
            init_msg_handler=lambda line: self.on_status(f"Tor: {line}"),
        )
        self.on_status(
            f"Private Tor ready (SOCKS {self.config.socks_host}:{self.config.socks_port}, "
            f"Control {self.config.control_host}:{self.config.control_port})"
        )

    def _start_listener(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.config.local_host, self.config.local_port))
        listener.listen(8)
        self._listener = listener
        local_port = listener.getsockname()[1]
        self.on_status(f"Listening on local port {local_port}")

        accept_thread = threading.Thread(target=self._accept_loop, name="accept-loop", daemon=True)
        accept_thread.start()
        self._threads.append(accept_thread)

    def _ensure_controller(self) -> Controller:
        if self._controller:
            return self._controller
        controller = Controller.from_port(address=self.config.control_host, port=self.config.control_port)
        if self.config.control_password:
            controller.authenticate(password=self.config.control_password)
        else:
            controller.authenticate()
        self._controller = controller
        return controller

    def _load_saved_private_key(self) -> tuple[str, str] | None:
        key_file = Path(self.config.onion_key_file)
        if not key_file.exists():
            return None
        raw = key_file.read_text(encoding="utf-8").strip()
        if ":" not in raw:
            return None
        key_type, key_value = raw.split(":", 1)
        if not key_type or not key_value:
            return None
        return key_type, key_value

    def _save_private_key(self, key_type: str, key_value: str) -> None:
        key_file = Path(self.config.onion_key_file)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(f"{key_type}:{key_value}\n", encoding="utf-8")

    def _clear_private_key(self) -> None:
        key_file = Path(self.config.onion_key_file)
        if key_file.exists():
            key_file.unlink()

    def _publish_onion_service(self, force_new: bool) -> None:
        if not self._listener:
            raise RuntimeError("Listener has not been started")
        local_port = self._listener.getsockname()[1]
        try:
            controller = self._ensure_controller()
            if self._service:
                controller.remove_ephemeral_hidden_service(self._service.service_id)
                self._service = None

            if force_new:
                self._clear_private_key()

            saved = self._load_saved_private_key()
            if saved:
                key_type, key_value = saved
                service = controller.create_ephemeral_hidden_service(
                    {self.config.virtual_port: local_port},
                    key_type=key_type,
                    key_content=key_value,
                    await_publication=True,
                )
            else:
                service = controller.create_ephemeral_hidden_service(
                    {self.config.virtual_port: local_port},
                    key_type="NEW",
                    key_content="ED25519-V3",
                    await_publication=True,
                )
                private_key = getattr(service, "private_key", None)
                private_key_type = getattr(service, "private_key_type", None)
                if private_key and private_key_type:
                    self._save_private_key(private_key_type, private_key)

            self._service = service
            self.own_onion = f"{service.service_id}.onion"
            self.on_status(f"Onion service ready: {self.own_onion}:{self.config.virtual_port}")
        except SocketError as exc:
            raise RuntimeError(
                "Could not connect to Tor control port. "
                "If private mode is disabled, make sure Tor is running and control port is enabled."
            ) from exc

    def _accept_loop(self) -> None:
        assert self._listener
        while not self._stop.is_set():
            try:
                conn, addr = self._listener.accept()
            except OSError:
                break
            thread = threading.Thread(target=self._connection_loop, args=(conn, f"{addr[0]}:{addr[1]}"), daemon=True)
            thread.start()
            self._threads.append(thread)

    def connect_peer(self, onion: str) -> None:
        address = onion.removesuffix(".onion") + ".onion"
        sock = socks.socksocket()
        sock.set_proxy(socks.SOCKS5, self.config.socks_host, self.config.socks_port)
        sock.settimeout(15)
        sock.connect((address, self.config.virtual_port))
        sock.sendall(encode_message("hello", self.own_onion or "unknown", ""))
        with self._conn_lock:
            self._connections[address] = sock
        thread = threading.Thread(target=self._connection_loop, args=(sock, address), daemon=True)
        thread.start()
        self._threads.append(thread)
        self.on_status(f"Connected to peer {address}")
        self.on_status(f"Peer online: {address}")

    def send_chat(self, onion: str, text: str) -> None:
        address = onion.removesuffix(".onion") + ".onion"
        with self._conn_lock:
            conn = self._connections.get(address)
        if conn is None:
            self.connect_peer(address)
            with self._conn_lock:
                conn = self._connections.get(address)
        if conn is None:
            raise RuntimeError(f"No connection available for {address}")
        conn.sendall(encode_message("msg", self.own_onion or "unknown", text))

    def _connection_loop(self, conn: socket.socket, peer_hint: str) -> None:
        peer_id = peer_hint
        conn.settimeout(1.0)
        recv_buffer = ""
        last_seen = time.monotonic()
        last_ping = 0.0
        announced_online = False

        def announce_online(current_peer: str) -> None:
            nonlocal announced_online
            if not announced_online:
                self.on_status(f"Peer online: {current_peer}")
                announced_online = True

        try:
            while not self._stop.is_set():
                now = time.monotonic()
                if now - last_ping >= self.HEARTBEAT_INTERVAL:
                    try:
                        conn.sendall(encode_message("ping", self.own_onion or "unknown", ""))
                        last_ping = now
                    except OSError:
                        self.on_status(f"Connection dropped: {peer_id}")
                        break

                try:
                    chunk = conn.recv(4096)
                except TimeoutError:
                    if announced_online and (time.monotonic() - last_seen) > self.PEER_TIMEOUT:
                        self.on_status(f"Connection dropped: {peer_id}")
                        break
                    continue
                except OSError:
                    self.on_status(f"Connection dropped: {peer_id}")
                    break

                if not chunk:
                    self.on_status(f"Connection dropped: {peer_id}")
                    break

                recv_buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in recv_buffer:
                    line, recv_buffer = recv_buffer.split("\n", 1)
                    message = decode_message(line.strip())
                    if not message:
                        continue

                    last_seen = time.monotonic()
                    candidate = message.sender.removesuffix(".onion") + ".onion"

                    if message.kind == "hello":
                        peer_id = candidate
                        with self._conn_lock:
                            self._connections[peer_id] = conn
                        announce_online(peer_id)
                        try:
                            conn.sendall(encode_message("hello", self.own_onion or "unknown", ""))
                        except OSError:
                            self.on_status(f"Connection dropped: {peer_id}")
                            break
                        continue

                    if message.kind == "ping":
                        peer_id = candidate
                        announce_online(peer_id)
                        try:
                            conn.sendall(encode_message("pong", self.own_onion or "unknown", ""))
                        except OSError:
                            self.on_status(f"Connection dropped: {peer_id}")
                            break
                        continue

                    if message.kind == "pong":
                        peer_id = candidate
                        announce_online(peer_id)
                        continue

                    if message.kind == "msg":
                        peer_id = candidate
                        announce_online(peer_id)
                        self.on_message(peer_id, message.text)
        finally:
            with self._conn_lock:
                if self._connections.get(peer_id) is conn:
                    self._connections.pop(peer_id, None)
            conn.close()
