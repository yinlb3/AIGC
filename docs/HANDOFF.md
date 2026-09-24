# HANDOFF — 交接说明

项目：`d:\Project\AIGC`（AI 检测工具箱，原作者 gxgx3456；接手时 v1.2.8，现行 v1.3.0）
本轮工作：代码审查、修复与实测验证（yinlb，2026-09）
细节见 `FIXES.md`（缺陷与改动）、`CALIBRATION.md`（数据）、`CHECK_FLOW.md`（改完怎么检）。

---

## 1. 当前状态

```
解释器：C:\ProgramData\miniconda3\envs\pytorch\python.exe
        Python 3.12.8 / torch 2.8.0+cu129 / transformers 5.17.0（勿降级）/ PySide6 6.9.2
        RTX 4080 SUPER 16GB
```

模型缓存由 `settings.json` 的 `download.models_dir` 指定 → `D:\hf_cache\aigc_models`（该文件不入库）。

**项目外数据（勿删）**

| 路径 | 内容 |
|---|---|
| `D:\hf_cache\aigc_models\` | 6 个引擎模型（simpleai 781MB / gltr 525MB / binoculars 1978MB / detectgpt 1378MB / fastdetectgpt 10239MB / zh_perplexity 803MB）|
| `D:\hf_cache\HC3_zh_all.jsonl` | HC3 中文原始（12,853 问），**现用**：展开成 pair 后配平 |
| `D:\hf_cache\ghostbuster-data\` | Ghostbuster 原件（英文 1.5GB）；**读时跳过** `logprobs/`、`other/`、`perturb/`、`prompts/` |
| `D:\hf_cache\zh_gpt2\` | 中文 GPT-2 |

**已弃用**（免得再被翻出来）：`hc3_zh_1to1.jsonl`（丢 question 致 94 条假重复）、`ghost_multi.jsonl`（69.8% 混入 logprobs）。
**定位**：中英双语论文查重，英文能力是正式功能。

---

## 2. 架构：两块

| | 内容 | 面向 |
|---|---|---|
| **第一部分** | `app/` + `installer/` —— 程序本体 | 用户 |
| **第二部分** | `tools/` —— 标定探针、评测、数据加载 | 开发者 |

标定值链路：`tools/probes/` → `tools/export_calibration.py` → `app/core/engines/engines_calibration.json` → 启动时由 `manager.py` 覆盖出厂值。
优先级：`catalog.py 出厂值 < 标定值 < 远端 < 用户覆盖`。

关键文件：`app/core/gpuinfo.py`（显卡探测，纯标准库）、`app/core/selfcheck.py`（启动自检 L1–L3）、
`installer/uninstaller.py`（独立卸载器 exe）、`tools/build_exe.ps1`（三步打包）。

---

## 3. 待办

**只剩 4 项**，按花费时间排序（依据见 `FIXES.md` §3）。

| 序 | 事项 | 耗时（实测） | 卡点 |
|---|---|---|---|
| 1 | **`fastdetectgpt` 中英标定** | **~5.5 小时**（中 15,216×1.01s + 英 5,984×0.65s）| 需排队用卡；7GB 显存红线实测不成问题 |
| 2 | `detectgpt` 中文换 `google/mt5-xl` → 标定 | 下载 ~1h + 标定 ~1.8h | 论文要求非英语用 mT5（`FIXES.md` §2.4）|
| 3 | **pyright 剩 5 条 `reportUnusedImport`** | 分钟级 | 用户要求如实记录、不做抑制，故 pending |
| 4 | **用新 exe 装一次复核** | ~30 分钟 | 本轮只做完静态与探针验证；待验：阈值框 50%、左右可拖、窗口能拉伸、英文不裁、勾旁检测按钮、赞赏码、PDF 多段、检测进度带耗时、首启下载不超 100%、卸载器有进度条 |

**已撤销 / 不做**：采样数 k 提到 100（误判 —— fast 路线无 k，见 `FIXES.md` §3）；
换论文的 Falcon-7B / T5-3B 与抓论文数据集（§1、§2.5）；改原作者文档；行长度与编码声明；并行数改下拉。

**已解决（别再翻）**：阈值收敛性（留出集落差 −0.58 点）、gltr 中文确认不可交付（改用 `zh_perplexity`）、
三个引擎标定值已由探针实跑写入 json、装机 / 界面 / 配置三探针、真装机实测、GLTR 四档柱状图、pyright 0 errors。

---

## 4. 关键决策

| # | 决策 | 理由 |
|---|---|---|
| 1 | **判据：是否影响用户使用效果** | 影响就修，不影响不动 |
| 2 | **代码风格跟随原作者** | 本项目有意偏离通行规范（见 `AUTHOR_STYLE.md`）|
| 3 | **阈值必须实测标定，不照抄论文** | 论文阈值绑定 Falcon-7B，量纲不可移植 |
| 4 | **不换论文的大模型** | 已实测「模型大小不是决定性的」（`FIXES.md` §1）|
| 5 | **标定值外置到 json** | 可追溯、改阈值不用重打包、删文件即回出厂值 |
| 6 | **原作者文档一律不改** | 待修订项记入 `FIXES.md` §4 |
| 7 | **原始数据不改，处理在进模型前做** | 无中间文件，只有一条数据路径 |
| 8 | **用户数据放安装目录** | `core.settings.base_dir()` 是唯一真源；放 `app\` 会被重装清掉 |

---

## 5. 注意事项（踩过的坑）

| # | 坑 | 说明 |
|---|---|---|
| 1 | 下载报 "outgoing traffic disabled" | 残留 `HF_HUB_OFFLINE=1` |
| 2 | 长任务没有输出 | 必须 `print(..., flush=True)`；先测单条耗时，预估 >30 分钟先报告 |
| 3 | **显存不足不报错，只变慢 10 倍** | Windows WDDM 换页；看**温度与功耗**判断，别只看利用率 |
| 4 | 引用指标必须写清数据集 | 同一阈值换数据集：93.67% → 52.33% |
| 5 | **清华 pytorch 源已 404** | 国内只有**上海交大**同时有 Windows wheel |
| 6 | **`docx` 不是 python-docx** | pip 名必须写 `python-docx` |
| 7 | **git 不读 Windows 系统代理** | 临时走：`git -c http.proxy=http://127.0.0.1:7890 push`（不写配置）|
| 8 | **改完必须重打 exe** | `tools/build_exe.ps1` 三步、**顺序不可反**；否则装出去的是旧代码（实测踩过）|
| 9 | PS 5.1 的 `Set-Content -Encoding UTF8` 会写 BOM | 带 BOM 的 json 让 `json.load` 抛异常 → 静默退化成默认值；写无 BOM 或读侧 `utf-8-sig` |
| 10 | `tm` 不等于页面坐标 | pypdf `visitor_text` 须用 `cm × tm` 才是真实坐标 |
| 11 | pip 下载途中的数据不在 `--cache-dir` | 在 `%TEMP%`；算进度要两部分都算并扣阶段基线 |
| 12 | 探针汇总的 `[BUG]` 未必是 bug | `Verdicts.add(ok=True)` 被当成"BUG 确认"，而 `package_flow` 传的是"通过" |

---

## 6. 文档索引

| 想了解 | 看哪个 |
|---|---|
| 有哪些缺陷、怎么修的 | `FIXES.md` |
| 与论文差在哪 | `FIXES.md` §2 |
| 各引擎实测数据 / 阈值依据 | `CALIBRATION.md` |
| **改完代码怎么检（五层流程）** | **`CHECK_FLOW.md`** |
| 代码风格基准（改动前必读） | `AUTHOR_STYLE.md` |
| 原作者文档待修订项 | `FIXES.md` §4 |
| 怎么复现验证 | `python tools/audit_probes.py --list` |
| 项目约定 | `AGENTS.md` |

**最常查的三个数字**：中文只有 `simpleai` 可交付（acc 0.9902 / AUC 0.9998）；
英文用 `gltr`（FPR≤5% 下 0.7659）或 `binoculars`（0.8422）；`fastdetectgpt` **未标定，别下结论**。

