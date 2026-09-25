"""segskip.py：段查找（段级布隆预检，跳过不含目标键的段）。"""
from __future__ import annotations

import hashlib
import json
import os

SNAPSHOT_PATH = "segskip.snapshot.json"
HASH_COUNT = 2


def _positions(key: str, bits: int) -> set:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    h1 = int.from_bytes(digest[:8], "big")
    h2 = int.from_bytes(digest[8:16], "big")
    return {(h1 + i * h2) % bits for i in range(HASH_COUNT)}


class Segments:
    def __init__(self, bits: int = 16, snapshot_path: str = SNAPSHOT_PATH):
        self.bits = bits
        self.snapshot_path = snapshot_path
        self.segments = []
        self.scanned = 0
        self.skipped = 0
        self.false_positives = 0

    def add_segment(self, seg_id: str, keys) -> dict:
        """增加一个段并记录其键集合。"""
        self.segments.append({"id": seg_id, "keys": set(keys), "filter": 0})
        return {"segments": len(self.segments)}

    def get(self, key: str) -> dict:
        """基线：每段都翻。"""
        self.scanned = len(self.segments)
        for segment in self.segments:
            if key in segment["keys"]:
                return {"found": True, "segment": segment["id"], "scanned": self.scanned}
        return {"found": False, "segment": None, "scanned": self.scanned}

    def build_filters(self) -> dict:
        """为每段构建段级布隆（bits 个位，每键至少两个散列位置置位）。"""
        for segment in self.segments:
            mask = 0
            for key in segment["keys"]:
                for pos in _positions(str(key), self.bits):
                    mask |= 1 << pos
            segment["filter"] = mask
        return {"filters": len(self.segments)}

    def lookup(self, key: str) -> dict:
        """先过布隆：任一位未置位就整段跳过；全部置位才读该段，命中即停。"""
        scanned = 0
        skipped = 0
        probes = _positions(str(key), self.bits)
        probe_mask = 0
        for pos in probes:
            probe_mask |= 1 << pos
        for segment in self.segments:
            if segment["filter"] & probe_mask != probe_mask:
                skipped += 1
                continue
            scanned += 1
            if key in segment["keys"]:
                self.scanned += scanned
                self.skipped += skipped
                return {"found": True, "segment": segment["id"],
                        "scanned": scanned, "skipped": skipped}
            self.false_positives += 1
        self.scanned += scanned
        self.skipped += skipped
        return {"found": False, "segment": None, "scanned": scanned, "skipped": skipped}

    def persist(self) -> bytes:
        """快照落盘，返回快照字节。"""
        blob = json.dumps({
            "bits": self.bits,
            "segments": [{"id": s["id"], "keys": sorted(s["keys"]), "filter": s["filter"]}
                         for s in self.segments],
        }).encode("utf-8")
        with open(self.snapshot_path, "wb") as fh:
            fh.write(blob)
        return blob

    def restore(self, blob: bytes = None) -> dict:
        """从快照恢复，段与位表与重启前一致。"""
        if blob is None:
            with open(self.snapshot_path, "rb") as fh:
                blob = fh.read()
        data = json.loads(blob.decode("utf-8"))
        self.bits = data["bits"]
        self.segments = [{"id": s["id"], "keys": set(s["keys"]), "filter": s["filter"]}
                         for s in data["segments"]]
        return {"segments": len(self.segments)}

    def stats(self) -> dict:
        return {"segments": len(self.segments), "scanned": self.scanned, "skipped": self.skipped,
                "false_positives": self.false_positives, "bits": self.bits}
