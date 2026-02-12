from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk, messagebox

from .config import TorConfig
from .network import TorChatNode
from .state import load_peers, save_peers


class XChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("XChat (Tor-style)")
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

        self._build_ui()
        self._load_saved_peers()
        self.root.after(150, self._poll_events)
        self.root.after(20, self._start_node)

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

        body = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=250)
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
        ttk.Button(peer_row, text="Paste", command=self._paste_peer_id).pack(side="left", padx=(6, 0))
        ttk.Button(peer_row, text="Add", command=self._add_peer).pack(side="left", padx=(6, 0))

        self.peer_list = tk.Listbox(left, bg="#f4f4f4", highlightthickness=1)
        self.peer_list.pack(fill="both", expand=True)
        self.peer_list.bind("<<ListboxSelect>>", self._on_peer_selected)
        self.peer_list.bind("<Double-1>", lambda _event: self._copy_selected_peer_id())
        self.peer_list.bind("<Delete>", lambda _event: self._remove_selected_peer())
        ttk.Button(left, text="Copy Peer ID", command=self._copy_selected_peer_id).pack(fill="x", pady=(6, 0))
        ttk.Button(left, text="Remove Peer", command=self._remove_selected_peer).pack(fill="x", pady=(6, 0))

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
        for peer in load_peers(self.node.config.peers_file):
            self._ensure_peer(peer)

    def _persist_peers(self) -> None:
        peers = list(self.peer_list.get(0, "end"))
        save_peers(self.node.config.peers_file, peers)

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

    def _copy_selected_peer_id(self) -> None:
        peer = self.active_peer.get().strip()
        if not peer:
            idx = self.peer_list.curselection()
            if idx:
                peer = self.peer_list.get(idx[0]).strip()
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

    def _remove_selected_peer(self) -> None:
        idx = self.peer_list.curselection()
        if not idx:
            messagebox.showwarning("No peer selected", "Select a peer to remove.")
            return
        peer = self.peer_list.get(idx[0])
        self.peer_list.delete(idx[0])
        if self.active_peer.get() == peer:
            self.active_peer.set("")
        self._persist_peers()
        self.status_label.configure(text=f"Peer removed: {peer}")

    def _refresh_my_id(self) -> None:
        confirmed = messagebox.askyesno(
            "Refresh Tor ID",
            "Generate a brand new Tor ID and make it permanent until next refresh?"
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
        except Exception as exc:
            messagebox.showerror("Tor startup failed", str(exc))
            self.status_label.configure(text=f"Error: {exc}")

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
                if self._ensure_peer(who):
                    self._persist_peers()
            else:
                self.status_label.configure(text=payload)
        self.root.after(150, self._poll_events)

    def _append_chat(self, line: str) -> None:
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", line + "\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _ensure_peer(self, peer: str) -> bool:
        items = self.peer_list.get(0, "end")
        if peer not in items:
            self.peer_list.insert("end", peer)
            return True
        return False

    def _add_peer(self) -> None:
        peer = self._normalize_peer_id(self.peer_input.get())
        if not peer:
            self.status_label.configure(text="Enter peer Tor ID first")
            return
        self._ensure_peer(peer)
        self.active_peer.set(peer)
        self.peer_input.set("")
        self._persist_peers()
        self.status_label.configure(text=f"Peer added: {peer}")

    def _on_peer_selected(self, _event: object) -> None:
        idx = self.peer_list.curselection()
        if not idx:
            return
        peer = self.peer_list.get(idx[0])
        self.active_peer.set(peer)
        self.status_label.configure(text=f"Active peer: {peer}")

    def _send_message(self) -> None:
        peer = self.active_peer.get().strip()
        text = self.message_entry.get().strip()
        if not peer:
            messagebox.showwarning("No peer selected", "Choose a peer from the left list before sending.")
            return
        if not text:
            return
        self.message_entry.delete(0, "end")
        try:
            self.node.send_chat(peer, text)
            self._append_chat(f"me → {peer}: {text}")
        except Exception as exc:
            self.status_label.configure(text=f"Send failed: {exc}")

    def shutdown(self) -> None:
        self.node.stop()
