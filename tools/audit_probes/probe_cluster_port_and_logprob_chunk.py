# -*- coding: utf-8 -*-
"""探针 v2a：2.4 集群端口 / 2.5 avg_logprob 分块。"""
import io
import socket
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"d:\Project\AIGC\app")

RESULT = []


def head(n, t):
    print("\n" + "=" * 68)
    print("【%s】%s" % (n, t))
    print("=" * 68)


def verdict(n, ok, detail):
    RESULT.append((n, ok, detail))
    print(">>> 结论: %s | %s" % ("BUG 确认" if ok else "未复现", detail))


# ---------------------------------------------------------------- 2.4
head("2.4", "集群发现端口被静默吞 —— cluster.py:59-66")
print('    try:\n        s.bind(("", DISCOVERY_PORT))\n    except OSError:\n        pass')
print()
PORT = 47650
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ok_bind = True
err = ""
try:
    s.bind(("", PORT))
except OSError as e:
    ok_bind = False
    err = "%s: %s" % (type(e).__name__, e)
print('bind(("", %d)) -> %s %s' % (PORT, "成功" if ok_bind else "失败", err))
s.close()

from core.cluster import ClusterMaster  # noqa: E402

print()
print("启动 ClusterMaster 5 秒:")
m = ClusterMaster()
m.start()
time.sleep(5)
nodes = m.nodes_snapshot()
print("    nodes_snapshot() = %r" % nodes)
m.stop()
print()
print("main_window.py:96:")
print('    if self.params.get("use_cluster") and self.master and self.master.nodes_snapshot():')
print("    nodes 为空 -> 永不进入集群分支，UI 无提示")
verdict("2.4", not nodes,
        "bind=%s，5 秒后 nodes=%r；集群分支要求 nodes 非空"
        % ("OK" if ok_bind else "FAIL", nodes))


# ---------------------------------------------------------------- 2.5
head("2.5", "avg_logprob 分块口径错 —— base.py:193-203")
print("        out = model(piece, labels=piece)")
print("        total += out.loss.item() * (end - begin)   # 权重用块长 L")
print("        n += end - begin")
print()
print("因果 LM 内部 shift：实际参与平均的是 L-1 个 token")
print()

import torch  # noqa: E402


class StubOut:
    def __init__(self, loss):
        self.loss = loss


class StubModel:
    def __call__(self, piece, labels=None):
        L = piece.size(1)
        return StubOut(piece.new_tensor(1.0 + 0.01 * L))


class Enc:
    pass


class StubTok:
    def __init__(self, n):
        self.n = n

    def __call__(self, text, **kw):
        e = Enc()
        e.input_ids = torch.arange(self.n).reshape(1, -1)
        return e


def avg_logprob(model, tok, chunk=256):
    ids = tok("x").input_ids
    if ids.size(1) < 2:
        return float("-inf")
    total, n = 0.0, 0
    with torch.no_grad():
        for begin in range(0, ids.size(1), chunk):
            end = min(begin + chunk, ids.size(1))
            piece = ids[:, begin:end]
            if piece.size(1) < 2:
                break
            out = model(piece, labels=piece)
            total += out.loss.item() * (end - begin)
            n += end - begin
            if end == ids.size(1):
                break
    return -(total / n) if n else float("-inf")


N = 100
tok = StubTok(N)
model = StubModel()
vals = {}
for ch in (1024, 50, 25, 10, 4):
    vals[ch] = avg_logprob(model, tok, chunk=ch)
    print("    chunk=%-5d -> avg_logprob = %.6f" % (ch, vals[ch]))
a, b = vals[1024], vals[25]
diff = abs(a - b) / abs(a) * 100
print()
print("单块(1024) vs 4块(25) 相对差 = %.4f%%" % diff)
print()
ids = torch.arange(N).reshape(1, -1)
tot2, n2 = 0.0, 0
with torch.no_grad():
    for begin in range(0, N, 1024):
        end = min(begin + 1024, N)
        out = model(ids[:, begin:end], labels=ids[:, begin:end])
        w = max(end - begin - 1, 1)
        tot2 += out.loss.item() * w
        n2 += w
print("正确权重(end-begin-1) 下单块 = %.6f" % (-(tot2 / n2)))
verdict("2.5", diff > 0.5,
        "chunk 变则结果变，相对差 %.4f%%（正确值应恒定）" % diff)


print("\n" + "#" * 68)
for n, o, d in RESULT:
    print("  [%s] %-5s %s" % ("BUG" if o else "OK ", n, d))
print("确认 bug: %d / %d" % (sum(1 for _, o, _ in RESULT if o), len(RESULT)))
