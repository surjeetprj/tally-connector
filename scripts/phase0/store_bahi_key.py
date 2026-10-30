"""Local masked API-key entry into Windows Credential Manager. No network calls."""
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import messagebox

REFERENCE = "InnoforiaTallyConnector/Phase0/Bahi/innoforia.com/201/h-bahi"


class Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def save_secret(value):
    raw = value.encode("utf-8")
    if len(raw) > 2560:
        raise ValueError("Key exceeds the credential storage size limit.")
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    row = Credential(Type=1, TargetName=REFERENCE, CredentialBlobSize=len(raw),
                     CredentialBlob=buffer, Persist=2, UserName="Bahi API")
    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    try:
        if not api.CredWriteW(ctypes.byref(row), 0):
            raise OSError(ctypes.get_last_error(), "Credential Manager write failed")
    finally:
        ctypes.memset(buffer, 0, len(raw))


def main():
    root = tk.Tk()
    root.title("Bahi connector — secure API key entry")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frame = tk.Frame(root, padx=22, pady=18)
    frame.pack()
    tk.Label(frame, text="Enter the Bahi test API key", font=("Segoe UI", 12, "bold")).pack(anchor="w")
    tk.Label(frame, justify="left", text=(
        "Server: https://innoforia.com/201/h-bahi/bahi/\n"
        "Expected business: SISOFT Technologies Private Limited (52)\n"
        "Business identity will be verified separately.\n\n"
        "Saved only in Windows Credential Manager. No network call is made."
    )).pack(anchor="w", pady=(8, 12))
    entry = tk.Entry(frame, show="*", width=64)
    entry.pack(fill="x")
    status = tk.Label(frame, text="", fg="red")
    status.pack(anchor="w", pady=5)

    def submit():
        value = entry.get().strip()
        if not value:
            status.config(text="Enter a key or choose Cancel.")
            return
        try:
            save_secret(value)
        except (OSError, ValueError):
            status.config(text="Could not save the key to Windows Credential Manager.")
            return
        entry.delete(0, tk.END)
        messagebox.showinfo("Key saved", "Saved in Windows Credential Manager.\n"
                            "The API has not been contacted or verified.", parent=root)
        root.destroy()

    buttons = tk.Frame(frame)
    buttons.pack(anchor="e")
    tk.Button(buttons, text="Cancel", command=root.destroy).pack(side="left", padx=8)
    tk.Button(buttons, text="Save securely", command=submit).pack(side="left")
    root.bind("<Return>", lambda event: submit())
    root.bind("<Escape>", lambda event: root.destroy())
    root.update_idletasks()
    root.geometry(f"+{max(0, (root.winfo_screenwidth()-root.winfo_width())//2)}"
                  f"+{max(0, (root.winfo_screenheight()-root.winfo_height())//2)}")
    entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
