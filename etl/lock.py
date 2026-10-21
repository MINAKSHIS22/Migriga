# MIGRIGA Analytics - Cross-process ETL lock
# Prevents two ETL runs (CLI and/or web) from writing the warehouse at the same time.
import os


class ETLAlreadyRunning(Exception):
    pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class ETLLock:
    def __init__(self, warehouse_path: str):
        self.path = os.path.abspath(warehouse_path) + ".etl.lock"
        self.fd = None

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        for _ in range(2):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                try:
                    with open(self.path) as f:
                        pid = int(f.read().strip() or 0)
                except (OSError, ValueError):
                    pid = 0
                if pid and _pid_alive(pid):
                    raise ETLAlreadyRunning("Another ETL run is already in progress.")
                # Stale lock left by a crashed process
                try:
                    os.remove(self.path)
                except FileNotFoundError:
                    pass
        raise ETLAlreadyRunning("Could not acquire the ETL lock.")

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
