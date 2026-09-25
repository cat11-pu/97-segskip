"""segskip.py：段查找（段级布隆预检，跳过不含目标键的段）。"""
from __future__ import annotations

import hashlib
import json
import os

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "segskip.snapshot.json")


class Segments:
    def __init__(self, bits: int = 16, hashes: int = 2, snapshot_path: str = SNAPSHOT_PATH):
        self.bits = bits
        self.hashes = max(2, hashes)
        self.snapshot_path = snapshot_path
        self.segments = []
        self.scanned = 0
        self.skipped = 0
        self.false_positives = 0
        self._built = False
        self._snapshot = None

    def add_segment(self, seg_id: str, keys) -> dict:
        """记录段及其键集合，过滤器留待 build_filters 统一构建。"""
        self.segments.append({"id": seg_id, "keys": set(keys), "filter": 0})
        self._built = False
        return {"segments": len(self.segments)}

    def get(self, key: str) -> dict:
        """基线：每段都翻。"""
        self.scanned = len(self.segments)
        for segment in self.segments:
            if key in segment["keys"]:
                return {"found": True, "segment": segment["id"], "scanned": self.scanned}
        return {"found": False, "segment": None, "scanned": self.scanned}

    def _positions(self, key: str) -> set:
        """双重散列：h2 强制为奇数，保证产生至少两个不同的槽位。"""
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        h1 = int.from_bytes(digest[:8], "big")
        h2 = int.from_bytes(digest[16:24], "big") | 1
        return {(h1 + i * h2) % self.bits for i in range(self.hashes)}

    def _mask(self, key: str) -> int:
        mask = 0
        for position in self._positions(key):
            mask |= 1 << position
        return mask

    def build_filters(self) -> dict:
        """为每段构建段级布隆过滤器，并落盘快照。"""
        for segment in self.segments:
            bits = 0
            for key in segment["keys"]:
                bits |= self._mask(key)
            segment["filter"] = bits
        self._built = True
        self.persist()
        return {"filters": len(self.segments)}

    def lookup(self, key: str) -> dict:
        """先过布隆：任一位未置位整段跳过；全部置位才读段，命中即停。"""
        if not self._built:
            self.build_filters()
        mask = self._mask(key)
        scanned = 0
        skipped = 0
        found_segment = None
        for segment in self.segments:
            if segment["filter"] & mask != mask:
                skipped += 1
                continue
            scanned += 1
            if key in segment["keys"]:
                found_segment = segment["id"]
                break
            self.false_positives += 1
        self.scanned += scanned
        self.skipped += skipped
        return {"found": found_segment is not None, "segment": found_segment,
                "scanned": scanned, "skipped": skipped}

    def persist(self) -> bytes:
        """快照落盘：段、键集合与位表。"""
        blob = json.dumps({
            "bits": self.bits,
            "hashes": self.hashes,
            "segments": [
                {"id": segment["id"], "keys": sorted(segment["keys"]), "filter": segment["filter"]}
                for segment in self.segments
            ],
        }, sort_keys=True).encode("utf-8")
        self._snapshot = blob
        try:
            with open(self.snapshot_path, "wb") as handle:
                handle.write(blob)
        except OSError:
            pass
        return blob

    def restore(self, blob: bytes = None) -> dict:
        """从快照恢复段与位表；blob 为空时取最近一次落盘的快照。"""
        if blob is None:
            blob = self._snapshot
        if blob is None and os.path.exists(self.snapshot_path):
            with open(self.snapshot_path, "rb") as handle:
                blob = handle.read()
        if blob is None:
            return {"segments": len(self.segments)}
        data = json.loads(blob.decode("utf-8"))
        self.bits = data["bits"]
        self.hashes = data["hashes"]
        self.segments = [
            {"id": item["id"], "keys": set(item["keys"]), "filter": item["filter"]}
            for item in data["segments"]
        ]
        self._built = True
        self._snapshot = blob
        return {"segments": len(self.segments)}

    def stats(self) -> dict:
        return {"segments": len(self.segments), "scanned": self.scanned, "skipped": self.skipped,
                "false_positives": self.false_positives, "bits": self.bits}
