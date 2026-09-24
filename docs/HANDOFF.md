# HANDOFF — 交接说明

项目：`d:\Project\AIGC`（AI 检测工具箱，原作者 gxgx3456；接手时 v1.2.8，现行 v1.3.0）
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

### 新增模块（2026-09-24）

| 模块 | 作用 |
|---|---|
| `app/core/gpuinfo.py` | 显卡 / CUDA 探测（**纯标准库**，零依赖）：读 `nvidia-smi` 的 `CUDA Version` → 选 `cuXXX` 索引；installer 与 first_run 共用同一份逻辑 |
| `app/core/selfcheck.py` | 启动自检 L1–L3（依赖存在性 + 真 import + CUDA 可用），实测约 1.5 秒；主程序在后台线程调用，有问题才提示 |
| `installer/uninstaller.py` | **独立卸载器**（2026-09-24 晚）：打包成 `dist/uninstaller.exe` 随安装分发，装机时复制到 `<安装目录>\uninstaller.exe` 并注册为卸载入口；不再生成 `.py` 交给 `pythonw` |
| `tools/build_exe.ps1` | **打包脚本**（三步，顺序不可反）：`uninstaller.exe` → `first_run_gui.exe` → `AIGC_Toolkit_Setup.exe`；顺带生成 `build_info.json`（版本 + git 短哈希 + 打包时间） |
| `tools/probes/env_setup.py` | 探针：路径校验 / CUDA 映射 / 卸载器（独立 exe）/ 进度解析 / 启动自检 |
| `tools/probes/display_marks.py` | 探针：四档和恒为 100 / 柱状图边界 / 引擎语言标注 |

---

## 3. 待办

**只剩 3 项**。按花费时间排序，有前置依赖的排后。（`FIXES.md` §3 有完整依据。）

| 序 | 事项 | 耗时（实测） | 卡点 |
|---|---|---|---|
| 1 | **`fastdetectgpt` 中英标定** | **~5.5 小时**（中 15,216×1.01s=4.3h + 英 5,984×0.65s=1.1h）| 显存 free 14.7GB，**7GB 红线实测不成问题**；需与下一项排队用卡 |
| 2 | `detectgpt` 中文换 `google/mt5-xl` → 标定 | 下载 ~1h + 标定 ~1.8h | 论文方案（`FIXES.md` §2.4）；扰动档按论文跑 `1,10,100` |
| 3 | **pyright 剩 5 条 `reportUnusedImport` warning** | 分钟级 | `app/core/engines/__init__.py` 的对外接口 / 探测导入；**用户要求如实记录、不做抑制**，故 pending |
| 4 | **用新 exe 装一次复核**（装机端到端）| ~30 分钟（含下 2~3GB 依赖）| 2026-09-24 晚只做完静态验证；待验：装完自动关闭、日志首行构建信息、`<安装目录>\uninstaller.exe` 到位、注册表 `UninstallString` 指向它、点它卸载能清干净 |

**已撤销**：「采样数 k 提到 100」—— 查证原文与官方仓库后确认是**误判**：
fast 路线的 `compute_crit()` 只做一次前向（解析式曲率，**没有 k 参数**），
k 只属于 detectgpt 的掩码扰动，且论文一次跑 `1,10,100` 三档对照，已并入上表第 2 项。
详见 `FIXES.md` §3。

**已确认不做**：换论文的 Falcon-7B / T5-3B 打分模型、抓论文数据集（`FIXES.md` §1、§2.5）；
改原作者文档；工程清理中的行长与编码声明。

### 进度条问题：已复现、已定位、已修（2026-09-24）

第二次标速按用户要求投到外部窗口、由用户**全程观察**，问题复现：
5 条跑完 5 步，进度条**停在 `1/5 = 20%`** 不再前进，明细却全打出来了（用户截图）。

**两个根因**：

1. 循环内用 `print` 输出明细，与 tqdm 抢同一行，把进度条挤停在中途
2. 每次只传 1 条文本调用引擎，`progress_cb` 的 `done` 每次从 1 重来，
   `bar.update(done - last)` 第二次起等于 `update(0)`，只走 1 步

**修法**：进度条活跃期输出一律用 `tqdm.write()`（禁用 `print`）；
逐条调用时每次调用前重置 `last = 0`。**两条已写入 skill**（真源 + 4 副本同步，
见 `FIXES.md` §8.6），标速脚本也已按此修好。

**影响**：只影响长任务的可观测性，不动主线功能、不改变产出结果。

**已解决**：

| 事项 | 结论 |
|---|---|
| 阈值收敛性 | ✅ 留出集验证无过拟合（落差 −0.58 点）|
| 划留出集 | ✅ `tools/probes/holdout.py` |
| gltr 中文 | ✅ 已重标，确认**不可交付**（FNR 73%）；用 `zh_perplexity` 替代 |
| **gltr / binoculars / simpleai 标定值** | ✅ **已全部由探针实跑写入 json**（此前是抄文档）|
| **装机 / 界面 / 配置测试** | ✅ 三个探针（`package_flow` / `ui_flow` / `ui_config`），见 `FIXES.md` §6 |
| **真装机实测** | ✅ **2026-09-24 实跑 `perform_install()` + 卸载**，含「装完读到的是标定值」验证，见 `FIXES.md` §6.5 |
| **GLTR 四档柱状图** | ✅ 2026-09-24 补上（原论文原产物），见 `FIXES.md` §8.1 |
| **静态检查** | ✅ `npx --yes pyright` = **0 errors**（配 `pyrightconfig.json`）；另有 5 条 `reportUnusedImport` warning 如实 pending，见 §3 待办 |

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
| 8 | **清华 pytorch 源已 404** | `mirrors.tuna.tsinghua.edu.cn/pytorch-wheels/` 整目录失效（实测）；国内只有**上海交大**同时有 `win_amd64`，阿里云 / 华为云只有 Linux 版 wheel |
| 9 | **git 不读 Windows 系统代理** | 它只认 `http.proxy` 配置或 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量。临时走代理：`git -c http.proxy=http://127.0.0.1:7890 push`（**不写任何配置**）|
| 10 | **`docx` 不是 python-docx** | PyPI 上的 `docx` 是 2014 年的另一个库，`pip install docx` 装错包；pip 名必须写 `python-docx` |
| 11 | **同步规则副本要按目录结构** | 拷错层级会造成"真源是新的、AI 读到的却是旧的"——`SKILL.md` 引用 `references/`，把文件拷到根层等于没生效（实测踩过，持续两天）|
| 12 | **改完必须重打 exe** | `tools/build_exe.ps1`，三步且**顺序不可反**（安装器把 `uninstaller.exe` 与整个 `app/` 当数据打进自己）。2026-09-24 实测装机装的是 9/19 的旧包：源码全改了，用户看到的全是旧现象 |
| 13 | **PS 5.1 的 `Set-Content -Encoding UTF8` 会写 BOM** | 带 BOM 的 json 会让 `json.load` 直接抛，`build_info` 静默退化成 `dev`。写无 BOM：`[IO.File]::WriteAllText($p, $s, (New-Object Text.UTF8Encoding($false)))`；读侧用 `utf-8-sig` 兜底 |
| 14 | **探针汇总里的 `[BUG]` 未必是 bug** | `Verdicts.add(tag, ok, …)` 把 `ok=True` 当"BUG 确认"，而 `package_flow` 传的是 `ok_all`（True=通过）→ 显示 `[BUG]` 但文字是"通过"。语义历史遗留，看正文不看标签 |

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

