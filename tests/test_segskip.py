import json
import threading
import unittest
import urllib.error
import urllib.request

from segskip import Segments
from server import serve

class TestSegments(unittest.TestCase):
    def test_add_counts(self):
        segments = Segments()
        self.assertEqual(segments.add_segment("s1", ["a"])["segments"], 1)

    def test_get_found(self):
        segments = Segments()
        segments.add_segment("s1", ["a"])
        self.assertEqual(segments.get("a")["segment"], "s1")

    def test_get_missing(self):
        segments = Segments()
        segments.add_segment("s1", ["a"])
        self.assertFalse(segments.get("zz")["found"])

    def test_stats_shape(self):
        self.assertIn("bits", Segments().stats())

    def test_http_add_get(self):
        server = serve(0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        urllib.request.urlopen(base + "/add", data=b'{"seg": "s1", "keys": ["a"]}', timeout=5).read()
        with urllib.request.urlopen(base + "/get", data=b'{"key": "a"}', timeout=5) as response:
            self.assertEqual(json.loads(response.read())["segment"], "s1")
        server.shutdown()


class TestBloomSkip(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.path = self.dir + "/snapshot.json"

    def make(self):
        segments = Segments(snapshot_path=self.path)
        segments.add_segment("s1", ["a", "b"])
        segments.add_segment("s2", ["c", "d"])
        segments.add_segment("s3", ["e", "f"])
        return segments

    def test_build_filters_counts(self):
        self.assertEqual(self.make().build_filters()["filters"], 3)

    def test_lookup_skips_without_scanning(self):
        segments = self.make()
        segments.build_filters()
        result = segments.lookup("d")
        self.assertEqual(result["segment"], "s2")
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["skipped"], 1)

    def test_lookup_miss_scans_nothing(self):
        segments = self.make()
        segments.build_filters()
        result = segments.lookup("z")
        self.assertIsNone(result["segment"])
        self.assertEqual(result["scanned"], 0)
        self.assertEqual(result["skipped"], 3)

    def test_lookup_matches_full_scan(self):
        segments = self.make()
        segments.build_filters()
        for key in ["a", "b", "c", "d", "e", "f", "z"]:
            self.assertEqual(segments.lookup(key)["segment"], segments.get(key)["segment"])

    def test_false_positives_observable(self):
        segments = self.make()
        segments.build_filters()
        segments.lookup("a")
        self.assertIn("false_positives", segments.stats())
        self.assertEqual(segments.stats()["false_positives"], 0)

    def test_persist_restore_roundtrip(self):
        segments = self.make()
        segments.build_filters()
        blob = segments.persist()
        clone = Segments(snapshot_path=self.dir + "/other.json")
        self.assertEqual(clone.restore(blob)["segments"], 3)
        self.assertEqual(clone.lookup("d")["segment"], "s2")
        self.assertEqual([s["filter"] for s in clone.segments],
                         [s["filter"] for s in segments.segments])

    def test_restore_from_disk_snapshot(self):
        segments = self.make()
        segments.build_filters()
        clone = Segments(snapshot_path=self.path)
        self.assertEqual(clone.restore()["segments"], 3)
