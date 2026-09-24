"""segskip.py：段查找（基线：逐段全扫）。"""
from __future__ import annotations


class Segments:
    def __init__(self, bits: int = 16):
        self.bits = bits
        self.segments = []
        self.scanned = 0
        self.skipped = 0

    def add_segment(self, seg_id: str, keys) -> dict:
        """基线：只存键集合，没有段级摘要。"""
        self.segments.append({"id": seg_id, "keys": set(keys)})
        return {"segments": len(self.segments)}

    def get(self, key: str) -> dict:
        """基线：每段都翻。"""
        self.scanned = len(self.segments)
        for segment in self.segments:
            if key in segment["keys"]:
                return {"found": True, "segment": segment["id"], "scanned": self.scanned}
        return {"found": False, "segment": None, "scanned": self.scanned}

    def build_filters(self) -> dict:
        raise NotImplementedError("段级布隆还没实现")

    def lookup(self, key: str) -> dict:
        raise NotImplementedError("预检跳过还没实现")

    def persist(self) -> bytes:
        raise NotImplementedError("快照还没实现")

    def restore(self, blob: bytes = None) -> dict:
        raise NotImplementedError("重启恢复还没实现")

    def stats(self) -> dict:
        return {"segments": len(self.segments), "scanned": self.scanned, "skipped": self.skipped,
                "bits": self.bits}
