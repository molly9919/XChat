from __future__ import annotations

from collections.abc import Callable
import socket
import threading
from typing import Any

import socks
from stem import SocketError
from stem.control import Controller

from .config import TorConfig
from .protocol import decode_message, encode_message

MessageCallback = Callable[[str, str], None]
StatusCallback = Callable[[str], None]


class TorChatNode:
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
        self.own_onion: str | None = None

    def start(self) -> None:
        self._start_listener()
        self._publish_onion_service()

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

    def _publish_onion_service(self) -> None:
        if not self._listener:
            raise RuntimeError("Listener has not been started")
        local_port = self._listener.getsockname()[1]
        try:
            controller = Controller.from_port(address=self.config.control_host, port=self.config.control_port)
            if self.config.control_password:
                controller.authenticate(password=self.config.control_password)
            else:
                controller.authenticate()
            service = controller.create_ephemeral_hidden_service(
                {self.config.virtual_port: local_port}, await_publication=True
            )
            self._controller = controller
            self._service = service
            self.own_onion = f"{service.service_id}.onion"
            self.on_status(f"Onion service ready: {self.own_onion}:{self.config.virtual_port}")
        except SocketError as exc:
            raise RuntimeError(
                "Could not connect to Tor control port. Make sure Tor is installed and control port is enabled."
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
        file = conn.makefile("r", encoding="utf-8", newline="\n")
        try:
            for line in file:
                message = decode_message(line.strip())
                if not message:
                    continue
                peer_id = message.sender
                if message.kind == "hello":
                    with self._conn_lock:
                        self._connections[peer_id] = conn
                    self.on_status(f"Peer online: {peer_id}")
                    continue
                if message.kind == "msg":
                    self.on_message(peer_id, message.text)
        except OSError:
            self.on_status(f"Connection dropped: {peer_id}")
        finally:
            with self._conn_lock:
                if self._connections.get(peer_id) is conn:
                    self._connections.pop(peer_id, None)
            conn.close()
            file.close()
