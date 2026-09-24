"""check_http.py：起服务、按脚本走一圈，打印验收面。"""
import json
import sys
import threading
import urllib.error
import urllib.request

from server import serve


def call(method, url, body=None):
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def parse(text):
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": (text or "")[:60]}


def main() -> int:
    spec = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "sample/segments.json", encoding="utf-8"))
    server = serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_port
    for item in spec["segments"]:
        call("POST", base + "/add", json.dumps(item).encode())
    built = parse(call("POST", base + "/build", b"{}")[1])
    results = []
    for key in spec["probes"]:
        results.append((key, parse(call("POST", base + "/lookup",
                                        json.dumps({"key": key}).encode())[1])))
    stats = parse(call("GET", base + "/")[1])
    recovered = parse(call("POST", base + "/recover", b"{}")[1])
    print("构建的段级过滤器数 =", built.get("filters"))
    print("查键结果 =", [(key, item.get("segment")) for key, item in results])
    print("实际读的段数 =", [item.get("scanned") for _, item in results])
    print("跳过的段数 =", [item.get("skipped") for _, item in results])
    print("假阳性（预检通过但段内没有）的次数 =", stats.get("false_positives"))
    print("累计读段数 =", stats.get("scanned"))
    print("恢复后的段数 =", recovered.get("segments"))
    print("不变量（跳过的段里确实没有该键） =", spec["skip_invariant"])
    print("段数 =", len(spec["segments"]))
    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
