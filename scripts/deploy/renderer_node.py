#!/usr/local/bin/python
"""Trusted Linux launcher: deny renderer networking without disabling app RPC."""

from __future__ import annotations

import ctypes
import errno
import os
import platform
import resource
import sys
import sysconfig
from pathlib import Path


class Filter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]


class Program(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]


def contain() -> None:
    """Fail closed on unknown ABI or unavailable seccomp; limits survive exec."""
    architecture = platform.machine()
    if architecture == "x86_64":
        audit, pair, sockets = 0xC000003E, 53, (41, 42, 43, 44, 45, 46, 47, 49, 50, 288)
    elif architecture == "aarch64":
        audit, pair, sockets = 0xC00000B7, 199, (198, 200, 201, 202, 203, 206, 207, 211, 212, 242)
    else:
        raise RuntimeError("unsupported renderer architecture")
    # Check seccomp_data.arch; unknown/x32 ABIs fail closed, then deny socket operations.
    instructions = [(0x20, 0, 0, 4), (0x15, 1, 0, audit), (0x06, 0, 0, 0x80000000),
                    (0x20, 0, 0, 0), (0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x80000000)]
    # libuv uses anonymous AF_UNIX socketpairs for child stdio (fc-match).
    # No named Unix sockets or network sockets can be created/connected.
    instructions.extend([(0x15, 0, 4, pair), (0x20, 0, 0, 16), (0x15, 1, 0, 1),
                         (0x06, 0, 0, 0x00050000 | errno.EPERM), (0x06, 0, 0, 0x7FFF0000)])
    for number in sockets:
        instructions.extend([(0x15, 0, 1, number), (0x06, 0, 0, 0x00050000 | errno.EPERM)])
    instructions.append((0x06, 0, 0, 0x7FFF0000))
    filters = (Filter * len(instructions))(*(Filter(*item) for item in instructions))
    program = Program(len(filters), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise RuntimeError("renderer seccomp unavailable")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    os.umask(0o077)


def main() -> None:
    candidates = {
        Path("/app/src/trust_receipt/reporting/assets/renderer/render.cjs").resolve(),
        (Path(sysconfig.get_path("purelib")) / "trust_receipt/reporting/assets/renderer/render.cjs").resolve(),
    }
    if (len(sys.argv) != 4 or sys.argv[1:3] != ["--max-old-space-size=128", "--disable-proto=throw"]
            or Path(sys.argv[3]).resolve() not in candidates):
        raise RuntimeError("invalid renderer invocation")
    contain()
    os.execv("/usr/local/bin/node", ["/usr/local/bin/node", *sys.argv[1:]])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("EXPORT_UNAVAILABLE")
        sys.exit(1)
