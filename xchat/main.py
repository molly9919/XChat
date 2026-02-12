from __future__ import annotations

import tkinter as tk

from .gui import XChatApp


def main() -> None:
    root = tk.Tk()
    app = XChatApp(root)

    def _on_close() -> None:
        app.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
