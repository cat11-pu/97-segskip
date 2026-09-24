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
