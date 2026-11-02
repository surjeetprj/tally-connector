"""Read the existing Credential Manager key without logging or copying it locally."""
import ctypes
from ctypes import wintypes

REFERENCE = "InnoforiaTallyConnector/Phase0/Bahi/innoforia.com/201/h-bahi"


class Credential(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]


def read_key():
    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    row = ctypes.POINTER(Credential)()
    if not api.CredReadW(REFERENCE, 1, 0, ctypes.byref(row)):
        raise ValueError("Existing Bahi credential is unavailable in Windows Credential Manager")
    try:
        return ctypes.string_at(row.contents.CredentialBlob, row.contents.CredentialBlobSize).decode("utf-8")
    finally:
        api.CredFree(row)
