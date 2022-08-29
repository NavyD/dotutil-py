import hashlib
import logging
from pathlib import Path
from subprocess import check_call


class SetupExcetion(Exception):
    pass


def get_digest(path: Path) -> str:
    h = hashlib.sha256()
    buf = memoryview(bytearray(128 * 1024))
    with open(path, "rb", buffering=0) as f:
        while n := f.readinto(buf):
            h.update(buf[:n])
    return h.hexdigest()


def has_changed(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    if not src.is_file():
        raise SetupExcetion(f"{src} is not a file")
    s = src.stat()
    d = dst.stat()
    return s.st_mode != d.st_mode or get_digest(src) != get_digest(dst)


def config_log(level=logging.CRITICAL):
    logging.basicConfig(format='%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(name)s.%(funcName)s]: %(message)s',
                        level=level,
                        datefmt='%Y-%m-%d %H:%M:%S')