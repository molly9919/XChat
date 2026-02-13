from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .config import TorConfig
from .network import TorChatNode
from .state import clear_message_cache, load_message_cache, load_peers, save_message_cache, save_peers


class XChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("XChat v 0.9 beta (Tor-style)")
        self.root.geometry("920x600")
        self.root.configure(bg="#d8d8d8")

        self.events: queue.Queue[tuple[str, str, str]] = queue.Queue()

        self.node = TorChatNode(
            config=TorConfig.from_env(),
            on_message=self._on_message,
            on_status=self._on_status,
        )
        self.active_peer = tk.StringVar()
        self.onion_id = tk.StringVar(value="Starting Tor service…")
        self.peer_input = tk.StringVar()
        self.peer_entry: ttk.Entry | None = None
        self.peer_tree: ttk.Treeview | None = None
        self.peer_status: dict[str, bool] = {}
        self.peer_context_menu: tk.Menu | None = None

        self.message_lock = threading.Lock()
        self.message_history: list[str] = []
        self.outbox: dict[str, list[str]] = {}

        self._load_icons()
        self._build_ui()
        self._load_message_cache()
        self._load_saved_peers()
        self.root.after(150, self._poll_events)
        self.root.after(20, self._start_node)

    @staticmethod
    def _make_circle_icon(size: int, fill_color: str) -> tk.PhotoImage:
        image = tk.PhotoImage(width=size, height=size)
        center = (size - 1) / 2
        radius = (size - 2) / 2
        for y in range(size):
            row_colors = []
            for x in range(size):
                dx = x - center
                dy = y - center
                if dx * dx + dy * dy <= radius * radius:
                    row_colors.append(fill_color)
                else:
                    row_colors.append("#d8d8d8")
            image.put("{" + " ".join(row_colors) + "}", to=(0, y))
        return image

    @staticmethod
    def _make_app_icon(size: int = 64) -> tk.PhotoImage:
        image = tk.PhotoImage(width=size, height=size)
        image.put("#2b2b36", to=(0, 0, size, size))

        def dot(cx: int, cy: int, r: int, color: str) -> None:
            for y in range(cy - r, cy + r + 1):
                if not 0 <= y < size:
                    continue
                row = []
                for x in range(cx - r, cx + r + 1):
                    if not 0 <= x < size:
                        continue
                    if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                        row.append(color)
                    else:
                        row.append("#2b2b36")
                image.put("{" + " ".join(row) + "}", to=(max(0, cx - r), y))

        def line(x0: int, y0: int, x1: int, y1: int, color: str) -> None:
            steps = max(abs(x1 - x0), abs(y1 - y0), 1)
            for i in range(steps + 1):
                t = i / steps
                x = round(x0 + (x1 - x0) * t)
                y = round(y0 + (y1 - y0) * t)
                image.put(color, to=(x, y, x + 1, y + 1))

        line(12, 18, 32, 12, "#8f88ad")
        line(32, 12, 50, 28, "#8f88ad")
        line(12, 18, 22, 40, "#8f88ad")
        line(22, 40, 38, 50, "#8f88ad")
        line(32, 12, 38, 50, "#8f88ad")
        line(50, 28, 38, 50, "#8f88ad")

        dot(12, 18, 6, "#82bac8")
        dot(32, 12, 6, "#ea8f82")
        dot(50, 28, 6, "#f1ca80")
        dot(22, 40, 6, "#58a0bf")
        dot(38, 50, 6, "#8bbfcd")
        dot(32, 30, 6, "#e86579")
        return image

    def _load_icons(self) -> None:
        self.icon_app = self._make_app_icon()
        self.icon_online = self._make_circle_icon(14, "#56d448")
        self.icon_offline = self._make_circle_icon(14, "#ef5350")
        self.root.iconphoto(True, self.icon_app)

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#d8d8d8")
        style.configure("TLabel", background="#d8d8d8")

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Your Tor ID:", font=("Sans", 11, "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.onion_id, foreground="#204a87").pack(side="left", padx=8)
        ttk.Button(top, text="Copy My ID", command=self._copy_my_id).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Refresh ID", command=self._refresh_my_id).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="Delete history", command=self._delete_all_messages).pack(side="left", padx=(6, 0))

        body = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=280)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ttk.Label(left, text="Peers", font=("Sans", 11, "bold")).pack(anchor="w")
        peer_row = ttk.Frame(left)
        peer_row.pack(fill="x", pady=6)
        self.peer_entry = ttk.Entry(peer_row, textvariable=self.peer_input)
        self.peer_entry.pack(side="left", fill="x", expand=True)
        self.peer_entry.bind("<Return>", lambda _event: self._add_peer())
        self.peer_entry.bind("<Control-v>", self._paste_peer_id_event)
        self.peer_entry.bind("<Control-V>", self._paste_peer_id_event)
        self.peer_entry.bind("<Shift-Insert>", self._paste_peer_id_event)
        self.peer_entry.bind("<Button-3>", self._show_peer_context_menu)
        self.peer_entry.bind("<Button-2>", self._show_peer_context_menu)
        self.peer_context_menu = tk.Menu(self.root, tearoff=0)
        self.peer_context_menu.add_command(label="Paste", command=self._paste_peer_id)
        self.peer_context_menu.add_command(label="Add", command=self._add_peer_from_entry_or_clipboard)
        ttk.Button(peer_row, text="Add", command=self._add_peer_from_entry_or_clipboard).pack(side="left", padx=(6, 0))

        self.peer_tree = ttk.Treeview(left, columns=(), show="tree", selectmode="browse", height=20)
        self.peer_tree.pack(fill="both", expand=True)
        self.peer_tree.bind("<<TreeviewSelect>>", self._on_peer_selected)
        self.peer_tree.bind("<Delete>", lambda _event: self._remove_selected_peer())
        peer_actions = ttk.Frame(left)
        peer_actions.pack(fill="x", pady=(6, 0))
        ttk.Button(peer_actions, text="Copy Peer ID", command=self._copy_selected_peer_id).pack(side="left", fill="x", expand=True)
        ttk.Button(peer_actions, text="Delete Peer ID", command=self._remove_selected_peer).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        self.chat_box = tk.Text(right, state="disabled", bg="#ffffff", wrap="word")
        self.chat_box.pack(fill="both", expand=True)

        input_row = ttk.Frame(right)
        input_row.pack(fill="x", pady=(8, 0))
        self.message_entry = ttk.Entry(input_row)
        self.message_entry.pack(side="left", fill="x", expand=True)
        self.message_entry.bind("<Return>", lambda _: self._send_message())
        ttk.Button(input_row, text="Send", command=self._send_message).pack(side="left", padx=(8, 0))

        self.status_label = ttk.Label(self.root, text="Ready", relief="sunken", anchor="w")
        self.status_label.pack(fill="x", side="bottom")

    def _load_saved_peers(self) -> None:
        loaded = False
        for peer in load_peers(self.node.config.peers_file):
            normalized = self._normalize_peer_id(peer)
            if normalized:
                self._ensure_peer(normalized, online=False)
                loaded = True
        if loaded:
            self._persist_peers()

    def _persist_peers(self) -> None:
        save_peers(self.node.config.peers_file, sorted(self.peer_status.keys()))

    def _load_message_cache(self) -> None:
        history, outbox = load_message_cache(self.node.config.message_cache_file)
        self.message_history = history
        self.outbox = outbox
        for line in history:
            self._append_chat(line, persist=False)

    def _persist_message_cache(self) -> None:
        with self.message_lock:
            save_message_cache(self.node.config.message_cache_file, self.message_history, self.outbox)

    def _copy_to_clipboard(self, value: str, label: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()
        self.status_label.configure(text=f"Copied {label}: {value}")

    def _copy_my_id(self) -> None:
        my_id = self.onion_id.get().strip()
        if not my_id or my_id.lower().startswith("starting"):
            self.status_label.configure(text="Your Tor ID is not ready yet")
            return
        self._copy_to_clipboard(my_id, "your Tor ID")

    def _selected_peer(self) -> str:
        if self.peer_tree is None:
            return ""
        selection = self.peer_tree.selection()
        if not selection:
            return ""
        return selection[0]

    def _copy_selected_peer_id(self) -> None:
        peer = self.active_peer.get().strip() or self._selected_peer()
        if not peer:
            messagebox.showwarning("No peer selected", "Select a peer ID to copy.")
            return
        self._copy_to_clipboard(peer, "peer Tor ID")

    def _paste_peer_id(self) -> None:
        try:
            raw = self.root.clipboard_get()
        except tk.TclError:
            self.status_label.configure(text="Clipboard is empty")
            return
        self.peer_input.set(str(raw).strip())
        if self.peer_entry:
            self.peer_entry.icursor("end")
            self.peer_entry.focus_set()
        self.status_label.configure(text="Peer ID pasted from clipboard")

    def _paste_peer_id_event(self, _event: tk.Event[tk.Misc]) -> str:
        self._paste_peer_id()
        return "break"

    def _add_peer_from_entry_or_clipboard(self) -> None:
        if not self.peer_input.get().strip():
            try:
                self.peer_input.set(str(self.root.clipboard_get()).strip())
            except tk.TclError:
                self.status_label.configure(text="Enter peer Tor ID first")
                return
        self._add_peer()

    def _show_peer_context_menu(self, event: tk.Event[tk.Misc]) -> str:
        if self.peer_context_menu is None:
            return "break"
        self.peer_context_menu.tk_popup(event.x_root, event.y_root)
        self.peer_context_menu.grab_release()
        return "break"

    @staticmethod
    def _normalize_peer_id(peer: str) -> str:
        value = peer.strip()
        if not value:
            return ""
        value = value.replace(" ", "")
        if ":" in value:
            value = value.split(":", 1)[0]
        if value.endswith(".onion"):
            return value.lower()
        return f"{value.lower()}.onion"

    @classmethod
    def _canonical_peer_id(cls, peer: str) -> str:
        return cls._normalize_peer_id(peer)

    def _update_peer_icon(self, peer: str) -> None:
        if self.peer_tree is None or peer not in self.peer_status:
            return
        icon = self.icon_online if self.peer_status[peer] else self.icon_offline
        self.peer_tree.item(peer, image=icon)

    def _set_peer_online(self, peer: str, online: bool) -> None:
        canonical = self._canonical_peer_id(peer)
        if not canonical:
            return
        added = self._ensure_peer(canonical, online=online)
        if not added:
            self.peer_status[canonical] = online
            self._update_peer_icon(canonical)
        self._persist_peers()
        if online:
            self._flush_outbox_async(canonical)

    def _flush_outbox_async(self, peer: str) -> None:
        threading.Thread(target=self._flush_outbox, args=(peer,), daemon=True).start()

    def _flush_outbox(self, peer: str) -> None:
        with self.message_lock:
            pending = list(self.outbox.get(peer, []))
        if not pending:
            return

        delivered = 0
        for text in pending:
            try:
                self.node.send_chat(peer, text)
            except Exception:
                break
            delivered += 1
            self.events.put(("status", "", f"Delivered queued message to {peer}"))

        if delivered <= 0:
            return

        with self.message_lock:
            remaining = self.outbox.get(peer, [])
            self.outbox[peer] = remaining[delivered:]
            if not self.outbox[peer]:
                self.outbox.pop(peer, None)
        self._persist_message_cache()

    def _queue_offline_message(self, peer: str, text: str) -> None:
        with self.message_lock:
            self.outbox.setdefault(peer, []).append(text)
        self._persist_message_cache()

    def _delete_all_messages(self) -> None:
        confirmed = messagebox.askyesno(
            "Delete history",
            "Delete all conversations, queued offline messages, and cached message data from this computer?",
        )
        if not confirmed:
            return
        with self.message_lock:
            self.message_history.clear()
            self.outbox.clear()
        clear_message_cache(self.node.config.message_cache_file)
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", "end")
        self.chat_box.configure(state="disabled")
        self.status_label.configure(text="All conversations and cached/offline messages deleted")

    def _remove_selected_peer(self) -> None:
        peer = self._selected_peer()
        if not peer:
            messagebox.showwarning("No peer selected", "Select a peer to remove.")
            return
        if self.peer_tree:
            self.peer_tree.delete(peer)
        self.peer_status.pop(peer, None)
        if self.active_peer.get() == peer:
            self.active_peer.set("")
        self._persist_peers()
        self.status_label.configure(text=f"Peer removed: {peer}")

    def _refresh_my_id(self) -> None:
        confirmed = messagebox.askyesno(
            "Refresh Tor ID",
            "Generate a brand new Tor ID and make it permanent until next refresh?",
        )
        if not confirmed:
            return
        try:
            new_id = self.node.refresh_identity()
            self.onion_id.set(new_id)
            self.status_label.configure(text=f"New Tor ID created: {new_id}")
        except Exception as exc:
            messagebox.showerror("Refresh failed", str(exc))
            self.status_label.configure(text=f"Refresh failed: {exc}")

    def _start_node(self) -> None:
        try:
            self.node.start()
            if self.node.own_onion:
                self.onion_id.set(self.node.own_onion)
            self._probe_saved_peers()
        except Exception as exc:
            messagebox.showerror("Tor startup failed", str(exc))
            self.status_label.configure(text=f"Error: {exc}")

    def _probe_saved_peers(self) -> None:
        peers = sorted(self.peer_status.keys())
        if not peers:
            return
        self.status_label.configure(text="Checking peer online status…")
        for peer in peers:
            threading.Thread(target=self._probe_one_peer, args=(peer,), daemon=True).start()

    def _probe_one_peer(self, peer: str) -> None:
        try:
            self.node.connect_peer(peer)
        except Exception:
            self.events.put(("status", "", f"Connection dropped: {peer}"))

    def _on_message(self, sender: str, text: str) -> None:
        self.events.put(("msg", sender, text))

    def _on_status(self, status: str) -> None:
        self.events.put(("status", "", status))

    def _poll_events(self) -> None:
        while True:
            try:
                event, who, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "msg":
                self._append_chat(f"{who}: {payload}")
                self._set_peer_online(who, True)
            else:
                if payload.startswith("Peer online: "):
                    self._set_peer_online(payload.removeprefix("Peer online: ").strip(), True)
                elif payload.startswith("Connection dropped: "):
                    self._set_peer_online(payload.removeprefix("Connection dropped: ").strip(), False)
                self.status_label.configure(text=payload)
        self.root.after(150, self._poll_events)

    def _append_chat(self, line: str, persist: bool = True) -> None:
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", line + "\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")
        if persist:
            with self.message_lock:
                self.message_history.append(line)
            self._persist_message_cache()

    def _ensure_peer(self, peer: str, online: bool = False) -> bool:
        if self.peer_tree is None:
            return False
        if peer in self.peer_status:
            return False
        self.peer_status[peer] = online
        icon = self.icon_online if online else self.icon_offline
        self.peer_tree.insert("", "end", iid=peer, text=peer, image=icon)
        return True

    def _add_peer(self) -> None:
        peer = self._normalize_peer_id(self.peer_input.get())
        if not peer:
            self.status_label.configure(text="Enter peer Tor ID first")
            return
        added = self._ensure_peer(peer, online=False)
        self.active_peer.set(peer)
        if self.peer_tree is not None:
            self.peer_tree.selection_set(peer)
            self.peer_tree.focus(peer)
        self.peer_input.set("")
        self._persist_peers()
        if added:
            self.status_label.configure(text=f"Peer added: {peer}")
        else:
            self.status_label.configure(text=f"Peer already exists: {peer}")

    def _on_peer_selected(self, _event: object) -> None:
        peer = self._selected_peer()
        if not peer:
            return
        self.active_peer.set(peer)
        self.status_label.configure(text=f"Active peer: {peer}")

    def _send_message(self) -> None:
        peer = self._canonical_peer_id(self.active_peer.get().strip())
        text = self.message_entry.get().strip()
        if not peer:
            messagebox.showwarning("No peer selected", "Choose a peer from the left list before sending.")
            return
        if not text:
            return

        self.message_entry.delete(0, "end")
        line = f"me → {peer}: {text}"
        try:
            self.node.send_chat(peer, text)
            self._append_chat(line)
        except Exception:
            self._append_chat(f"{line} [queued for offline delivery]")
            self._queue_offline_message(peer, text)
            self.status_label.configure(text=f"Peer offline, message queued: {peer}")

    def shutdown(self) -> None:
        self._persist_peers()
        self._persist_message_cache()
        self.node.stop()
