from __future__ import annotations

import ctypes
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name: str) -> None:
        self.name = name
        self.handle: int | None = None

    def acquire(self) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        kernel32.CreateMutexW.restype = wintypes.HANDLE

        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = int(handle)
        return mutex_was_acquired(ctypes.get_last_error())

    def release(self) -> None:
        if self.handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle(self.handle)
        self.handle = None

    def __enter__(self) -> SingleInstance:
        if not self.acquire():
            raise AlreadyRunningError(f"{self.name} is already running")
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.release()


class AlreadyRunningError(RuntimeError):
    pass


def mutex_was_acquired(last_error: int) -> bool:
    return last_error != ERROR_ALREADY_EXISTS
