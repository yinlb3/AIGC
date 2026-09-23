# HANDOFF — 交接说明

项目：`d:\Project\AIGC`（AI 检测工具箱 v1.2.8，原作者 gxgx3456）
本轮工作：代码审查、修复与实测验证（yinlb，2026-09）
细节见 `FIXES.md`（缺陷与改动）、`CALIBRATION.md`（数据）、`CHECK_FLOW.md`（检测流程）。

---

## 1. 当前状态

### 环境

```
解释器：C:\ProgramData\miniconda3\envs\pytorch\python.exe
        Python 3.12.8 / torch 2.8.0+cu129 / transformers 5.17.0（勿降级）/ PySide6 6.9.2
        RTX 4080 SUPER 16GB
```

### 项目外数据（勿删）

| 路径 | 内容 |
|---|---|
| `D:\hf_cache\aigc_models\` | 5 个模型（simpleai 781MB / gltr 525MB / binoculars 1978MB / detectgpt 1378MB / fastdetectgpt 10239MB）|
| `D:\hf_cache\ghostbuster-data\` | Ghostbuster 原件（英文，1.5GB）。**读时须跳过** `logprobs/`（token+概率，非文本）、`other/`（仅人写无 AI）、`perturb/`、`prompts/` |
| `D:\hf_cache\HC3_zh_all.jsonl` | HC3 中文原始（12,853 问）—— **现用**，展开成 pair 后配平 |
| `D:\hf_cache\hc3_zh_1to1.jsonl` | 旧 1:1 集（3000 条，**已弃用**：丢 question 致 94 条假重复）|
| `D:\hf_cache\ghost_multi.jsonl` | **已弃用**：69.8% 混入 logprobs 格式，不可用 |
| `D:\hf_cache\zh_gpt2\` | 中文 GPT-2 |

模型缓存由 `settings.json` 的 `download.models_dir` 指定（该文件在 `.gitignore` 内）。

### 定位变更

项目从「中文论文查重」调整为**「中英双语论文查重」**。英文能力自此是正式功能。

---

## 2. 架构：两块

| | 内容 | 面向 |
|---|---|---|
| **第一部分** | `app/` + `installer/` —— 程序本体（原作者写的 + 本次修正）| 用户 |
| **第二部分** | `tools/` —— 标定探针、评测、数据加载 | 开发者 |

**标定值走第二部分产出 → 落盘 → 第一部分读取**（见 `AGENTS.md`「标定值必须外置」）：

```
tools/probes/  →  tools/export_calibration.py  →  app/core/engines/engines_calibration.json
                                                            ↓ 启动时读取
                                                     manager.py 覆盖出厂值
```

优先级：`catalog.py 出厂值 < 标定值 < 远端 < 用户覆盖`

---

## 3. 待办

**只列没做的**。做完的见 `FIXES.md`。

| 优先级 | 事项 | 卡点 |
|---|---|---|
| 高 | **`fastdetectgpt` 中英标定** | 需可用显存 ≥7GB。**唯一没数据的主力引擎** |
| 高 | **`detectgpt` 中文换 mT5 扰动模型** | ✅ 论文给了方案（`FIXES.md` §2.4）：非英语要用 mT5。改清单即可，不用改代码 |
| 中 | 采样数 k 提到 100 | 论文说 k=100 才收敛；慢 10~20 倍 |
| 低 | **GLTR 四档柱状图**（论文原产物是涂色图 + 直方图）| **数字版已做**（每段下方一行「绿 x% │ 黄 x% │ 红 x% │ 紫 x%」），柱状图未做 |

**已确认不做**：换论文的 Falcon-7B / T5-3B 打分模型、抓论文数据集（`FIXES.md` §1、§2.5）；
改原作者文档；工程清理中的行长与编码声明。

**已解决**：

| 事项 | 结论 |
|---|---|
| 阈值收敛性 | ✅ 留出集验证无过拟合（落差 −0.58 点）|
| 划留出集 | ✅ `tools/probes/holdout.py` |
| gltr 中文 | ✅ 已重标，确认**不可交付**（FNR 73%）；用 `zh_perplexity` 替代 |
| **gltr / binoculars / simpleai 标定值** | ✅ **已全部由探针实跑写入 json**（此前是抄文档）|
| **装机 / 界面 / 配置测试** | ✅ 三个探针（`package_flow` / `ui_flow` / `ui_config`），见 `FIXES.md` §6 |
| **静态检查** | ✅ `npx --yes pyright` = 0 errors（配 `pyrightconfig.json`）；抓出 3 个"从没跑过所以没人发现"的错，见 `FIXES.md` §6.2 |


---

## 4. 关键决策

| # | 决策 | 理由 |
|---|---|---|
| 1 | **判据：是否影响用户使用效果** | 影响就修，不影响不动 |
| 2 | **代码风格跟随原作者** | 本项目有意偏离通行规范（见 `AUTHOR_STYLE.md`）|
| 3 | **阈值必须实测标定，不照抄论文** | 论文阈值绑定 Falcon-7B，量纲不可移植 |
| 4 | **不换论文的大模型** | 已实测「模型大小不是决定性的」（见 `FIXES.md` §1）|
| 5 | **标定值外置到 json** | 可追溯、改阈值不用重打包、删文件即回出厂值 |
| 6 | **原作者文档一律不改** | 待修订项记入 `FIXES.md` §4 |
| 7 | **原始数据不改，处理在进模型前做** | 无中间文件，只有一条数据路径 |

---

## 5. 注意事项（踩过的坑）

| # | 坑 | 说明 |
|---|---|---|
| 1 | `HF_HUB_OFFLINE=1` 残留 | 会让下载报 "outgoing traffic disabled" |
| 2 | 长任务必须带进度 | `print(..., flush=True)`，flush 不加则输出被缓冲 |
| 3 | **显存不足不报错，只变慢 10 倍** | Windows WDDM 把数据换到内存；看**温度和功耗**判断，别只看利用率 |
| 4 | σ 归一化在小采样下反而有害 | 论文用 k=100，我们用 5~10 |
| 5 | **引用指标必须说明数据集** | 同一阈值换数据集，93.67% → 52.33% |
| 6 | `settings.json` 含本机路径 | 发布前需删或改回默认 |
| 7 | 单条耗时须先测 | `python tools/estimate_timing.py`；预估 >30 分钟先报告 |

---

## 6. 文档索引

| 想了解 | 看哪个 |
|---|---|
| 有哪些缺陷、怎么修的 | `docs/FIXES.md` |
| 与论文差在哪 | `docs/FIXES.md` §2 |
| 各引擎实测数据 / 阈值依据 | `docs/CALIBRATION.md` |
| **改完代码怎么检**（五层流程）| **`docs/CHECK_FLOW.md`** |
| 代码风格基准（改动前必读） | `docs/AUTHOR_STYLE.md` |
| 原作者文档待修订项 | `docs/FIXES.md` §4 |
| 怎么复现验证 | `python tools/audit_probes.py --list` |
| 项目约定 | `AGENTS.md` |

**最常查的三个数字**：

| 问题 | 答案 | 出处 |
|---|---|---|
| 中文用哪个引擎？ | **只有 simpleai 可交付**（15,216 条实测 acc 0.9902 / AUC 0.9998）| `CALIBRATION.md` §1 |
| 英文用哪个引擎？ | **gltr（FPR≤5% 下 0.7659）或 binoculars（0.8422）** | `CALIBRATION.md` §2 |
| `fastdetectgpt` 能用吗？ | **未标定，别下结论** | `CALIBRATION.md` §1.1 |

