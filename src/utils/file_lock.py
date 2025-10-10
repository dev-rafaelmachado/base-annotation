"""
Sistema de lock de arquivo para evitar conflitos de escrita
"""
import os
import time
from pathlib import Path
from typing import Optional


class FileLock:
    """Lock de arquivo simples para evitar escrita simultânea"""

    def __init__(self, lock_file: Path, timeout: int = 10):
        self.lock_file = lock_file
        self.timeout = timeout
        self.lock_acquired = False

    def acquire(self) -> bool:
        """Tenta adquirir o lock"""
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # Tenta criar arquivo de lock (exclusivo)
                if not self.lock_file.exists():
                    self.lock_file.touch()
                    self.lock_acquired = True
                    return True

                # Lock já existe, espera um pouco
                time.sleep(0.1)
            except Exception:
                time.sleep(0.1)

        return False

    def release(self):
        """Libera o lock"""
        if self.lock_acquired and self.lock_file.exists():
            try:
                self.lock_file.unlink()
                self.lock_acquired = False
            except Exception:
                pass

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(
                f"Não foi possível adquirir lock em {self.timeout}s")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
