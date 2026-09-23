# -*- coding: utf-8 -*-
"""探针 v8：2.4b 集群 —— 启动真工作节点，验证发现与分发链路。"""
import io
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"d:\Project\AIGC\app")

print("=" * 68)
print("【2.4b】集群发现链路（本机同时跑 master + worker）")
print("=" * 68)

from core.cluster import DISCOVERY_PORT, TASK_PORT, ClusterMaster, ClusterWorker  # noqa: E402

print("DISCOVERY_PORT = %d, TASK_PORT = %d" % (DISCOVERY_PORT, TASK_PORT))
print()
print("配置 A) 用 use_cluster 开关观察 master 是否自行启动")
print("   main_window.py:679 传入 master 的条件:")
print('       self.master if params.get("use_cluster") else None')
print("   main_window.py:533 on_cluster_toggled 会在勾选时 master.start()")
print()

logs = []
m = ClusterMaster(on_log=lambda s: logs.append(s))
w = ClusterWorker(engine_factory=lambda eid: None, on_log=lambda s: logs.append("W:" + s))
print("启动 worker（worker.start() 内部自动开 UDP/TCP 监听）")
w.start()
time.sleep(1)
print("启动 master")
m.start()
print()
print("等待 8 秒观察发现过程...")
for i in range(8):
    time.sleep(1)
    snap = m.nodes_snapshot()
    if snap:
        print("   第 %d 秒: 发现 %d 个节点 -> %r" % (i + 1, len(snap), snap))
        break
else:
    snap = m.nodes_snapshot()
    print("   8 秒后仍未发现节点: %r" % snap)

print()
print("--- 日志 ---")
for s in logs[:25]:
    print("   %s" % s)
if not logs:
    print("   (无日志)")
print()

print("配置 B) worker 绑定 %d，master 绑定同一个端口会不会冲突" % DISCOVERY_PORT)
import socket  # noqa: E402

s1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
r1 = "OK"
try:
    s1.bind(("", DISCOVERY_PORT))
except OSError as e:
    r1 = "FAIL %s" % e
s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
r2 = "OK"
try:
    s2.bind(("", DISCOVERY_PORT))
except OSError as e:
    r2 = "FAIL %s" % e
print("   第一个 socket bind: %s" % r1)
print("   第二个 socket bind: %s" % r2)
print("   -> SO_REUSEADDR 下两者都能绑定，UDP 单播回包只会送到其中一个")
print()
s1.close()
s2.close()

print("配置 C) master 是否能分发任务到 worker（用桩引擎）")
try:
    w.stop()
    time.sleep(0.5)
    import json

    from core.cluster import _recv_json, _send_json

    class StubEngine:
        def predict_paragraphs(self, paragraphs, device, progress_cb=None, **kw):
            return [0.77] * len(paragraphs)

    w2 = ClusterWorker(engine_factory=lambda eid: StubEngine(),
                       on_log=lambda s: logs.append("W2:" + s))
    w2.start()
    time.sleep(1)
    ok_direct = None
    try:
        with socket.create_connection(("127.0.0.1", TASK_PORT), timeout=5) as c:
            c.settimeout(20)
            _send_json(c, {"type": "detect", "engine": "stub",
                           "paragraphs": ["测试一", "测试二"],
                           "params": {}})
            resp = _recv_json(c)
        ok_direct = resp
        print("   直接连 worker TASK_PORT 发任务 -> %r" % resp)
    except Exception as e:
        print("   直接分发失败: %s: %s" % (type(e).__name__, e))
    w2.stop()
except Exception as e:
    import traceback

    print("   分发测试异常: %s: %s" % (type(e).__name__, e))
    traceback.print_exc(limit=2)

m.stop()
w.stop()
print()
print(">>> 结论: 见上方发现结果；若 nodes 始终为空，")
print("          则 main_window.py:96 的集群分支永远走不到。")
