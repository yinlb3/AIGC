# 缺陷与差异记录

- 对象：`d:\Project\AIGC`（v1.2.8，原作者 gxgx3456）
- 审查与修复：yinlb，2026-09
- 环境：`C:\ProgramData\miniconda3\envs\pytorch`（torch 2.8.0+cu129 / RTX 4080S 16GB）
- 复现：`python tools/audit_probes.py --list`
- 本文件合并自原 `AUDIT.md` + `PAPER_GAPS.md` + `DOC_FIXES_PENDING.md`

**只看结论**：§1 修了什么 → §2 与论文的差异 → §3 待办 → §4 原作者文档待改 → §5 改动清单

---

## 1. 已修的缺陷

| # | 问题 | 位置 | 效果 |
|---|---|---|---|
| 1 | **Binoculars 恒判 AI**（分母跑出 log 域 + 无交叉项 + 量纲混用）| `binoculars_engine.py` | 准确率 46.7% → **94.17%** |
| 2 | **`avg_logprob` 分块口径错**（影响面最广：binoculars/perplexity/curvature 的公共基座）| `base.py` | 偏差 34~67% → **0.000%** |
| 3 | 设置保存写坏 `hf_endpoint`（丢协议头）→ 模型下载全失败 | `settings_dialog.py` | 下载恢复 |
| 4 | 集群发现被端口绑定竞争掐死 | `cluster.py` | 恒为空 → **4 秒发现节点** |
| 5 | detectgpt / fastdetectgpt 缺 σ 归一化 | `curvature_engine.py` | 补上（实测与论文相悖，见 §2.4）|
| 6 | 引擎清单参数覆盖用户参数 | `main_window.py` | 顺序修正 |
| 7 | 中文长文本超 `n_positions` 崩溃 | `base.py` | 新增 `_encode_capped()` |
| 8 | 显存不足静默降速（fp32 溢出）| `base.py` | fp16 加载 + 显存预检三档 |
| 9 | T5 输入超 512 token | `curvature_engine.py` | 两侧截断 |
| 10 | 报告文件名未转义 / `smoke_test.py` 路径错 | `report.py` / `tools/` | 修 |
| 11 | 引擎无语言标注 → 用户误用（detectgpt 中文判定**反向**）| `engine_dialog.py` 等 | 加 ✅/⚠️/❌ 标注 |
| 12 | 阈值不可移植 | `catalog.py` | 重标（见 `CALIBRATION.md`）|
| 13 | `zh_perplexity` 阈值错（FPR 95%）| 标定数据 | 修正，FPR 4% |
| 14 | **工程清理** | 11 个文件 | 删 17 处未用导入（行长/编码声明按规范**不动**）|

**未修（非缺陷）**：BUG-9 gltr 命名（设计决策）、BUG-10 license 空壳（原作者决定）、
BUG-18 gltr 在长文/新闻类判别力弱（方法局限）。

### 关键结论：模型大小不是决定性的

| 引擎 | 模型规模 | 中文结果 |
|---|---|---|
| simpleai | ~0.1B | **99.75%** |
| binoculars | ~0.4B | 英文 94.17% |
| Binoculars 修前→修后（**模型未变**）| — | 46.7% → **94.17%** |

**决定性的是「代码对 + 阈值标定 + 语言匹配」。** 所以不换论文的 Falcon-7B / T5-3B
（**但非英语的扰动模型要换 mT5 —— 论文明确要求，见 §2.4**）。

---

## 2. 与论文的差异

分级：**S** 影响结论 → **A** 影响数值 → **B** 需研究 → **C** 无影响

### 2.1 S 级：数据语言

论文（arXiv:2401.12070v3 §5.2）承认多语言是弱项，**其检测器只针对英文**。
本项目用英文模型处理中文 → 部分引擎在中文上不可用（实测见 `CALIBRATION.md`）。

**这是最影响结论的差异**：中文侧只有 `simpleai` 可交付。

### 2.2 A 级：公式实现（已修）

| 论文 | 修复前 | 现状 |
|---|---|---|
| Binoculars §3.3 式 (3)(4)：分母留 log 域 + 交叉项 + 同量纲比 | `exp()` 出域、无交叉项、log/实数 | ✅ 按论文 |
| DetectGPT / Fast §2.3：σ 归一化 | 缺 | ✅ 补上（效果见 §2.4）|
| GLTR §3 Test-2：rank 四档 | 只做整段 PPL | ✅ 实现为 `method="rank"` 可选 |

### 2.3 B 级：模型规模

| 引擎 | 论文 | 本项目 | 差 |
|---|---|---|---|
| Binoculars | Falcon-7B / 7B-Instruct | gpt2 / gpt2-medium | ~20~30 倍 |
| DetectGPT | T5-3B | t5-base | ~15 倍 |
| Fast-DetectGPT | Neo-2.7B / GPT-J | gpt-neo-2.7B | ✅ 基本一致 |

**不换的理由见 §1「模型大小不是决定性的」。**

### 2.4 B 级：σ 归一化（实测与论文相悖）+ 非英语扰动模型

**前半：σ 归一化**

论文 §5.3：`accuracy continues to improve until 100 perturbations, where it converges`。
本项目 `k=5~10`（论文 100 / 10000）→ **σ 估不稳，归一化反而有害**：

| | 未归一化 | 加了 σ 归一化 |
|---|---|---|
| detectgpt 英文 | acc 90% | AUC **0.7100**（论文 0.9554）|

**后半：非英语要用 mT5（论文明确要求，我们没做）**

DetectGPT 论文 §6 Limitations 原文：

> While in this work, we use off-the-shelf mask-filling models such as T5 and
> **mT5 (for non-English languages)**, some domains may see reduced performance
> if existing mask-filling models do not well represent the space of meaningful
> rephrases, reducing the quality of the curvature estimate.

| | 论文 | 本项目 |
|---|---|---|
| 英文扰动模型 | T5-3B | t5-base ✅ 同族 |
| **非英语扰动模型** | **mT5** | ❌ 仍用 t5-base（英文）|

**这是 detectgpt 中文 AUC 0.2800（反向）的一个成因** —— 不是"中文 T5 生态弱所以做不了"，
而是**我们用错了模型族**。论文给了出路。

**好消息**：`curvature_engine._mask_perturb` 用的是 `<extra_id_N>` 哨兵格式，
**mT5 同格式**，所以换模型**只需改清单的 `models` 字段**（第 2 个 model 的 `repo`），
**不用改代码**。


### 2.5 B 级：标定数据与样本量

| | 论文（附录 A.1.2）| 本项目 |
|---|---|---|
| 数据 | CC News + CNN + PubMed（**需自己抓语料 + 用 LLaMA-2-13B 生成**）| HC3（中）+ Ghostbuster（英），公开可下载 |
| 样本量 | 每数据集 **500 条** | 15,216（中）/ 21,268（英）|
| 人机比 | 严格 1:1 | 按论文 §4.1 配平 ✅ |
| 标定目标 | maximize accuracy | ✅ 一致 |

**论文用的数据集我们做不了**（要 13GB 模型 + 数小时生成），且**数据集不同则指标不可直接比**
（实测：同一引擎同一阈值，换数据集从 93.67% 掉到 52.33%）。

**论文的留出集设计我们没做**：它明确区分「标定用」与「out-of-domain 评测用」
（`we do not include them in the threshold determination`）。我们同批数据既标定又评测，
**指标偏乐观**。

### 2.6 C 级：无影响项

- `max_tokens` 差异
- 阈值搜索步长与候选数

---

## 3. 待办

**只剩 4 项**（前 3 项已解决，见下）。按花费时间排序，有前置依赖的排后。

| 优先级 | 事项 | 耗时（实测更新） | 卡点 |
|---|---|---|---|
| 中 | `detectgpt` 中文换 **mT5**（论文用 `google/mt5-xl`）→ 标定 | 下载 ~1 小时 + 标定 ~1.8 小时 | 论文给了方案（见 §2.4）；扰动档按论文跑 `1,10,100` |
| 高 | **`fastdetectgpt` 中英标定** | **~5.5 小时**（两次实测：中 15,216×1.01s = 4.3h + 英 5,984×0.65s = 1.1h；模型加载 21 秒）| 显存 free 14.7GB，**7GB 红线已不成问题**（实测）；须与上一项排队用卡 |
| 低 | **pyright 剩 5 条 `reportUnusedImport` warning** | `app/core/engines/__init__.py`：4 条对外接口导入（`BUILTIN_ENGINES` / `EngineManager` / `load_plugins` / `register`）+ 1 条 `try: import torch` 探测导入。2026-09-24 曾用单行 `# pyright: ignore[...]` 抑制，**用户要求改为如实记录、不做抑制**，故 pending |
| 高 | **用新 exe 装一次复核**（装机端到端）| ~30 分钟（含下 2~3GB 依赖）。2026-09-24 晚只做完静态验证：待验「装完自动关闭 / 日志首行构建信息 / `<安装目录>\uninstaller.exe` 到位 / 注册表 `UninstallString` 指向它 / 点它卸载能清干净」—— 见 §8.10 |

### 原「k 提到 100」已撤销（2026-09-24）

**查了原文与官方仓库，这个待办本身是误判**：

| 来源 | 事实 |
|---|---|
| `fast-detect-gpt/scripts/local_infer.py` | `compute_crit()` **只做一次前向**就出曲率，**没有 k / n_samples / 采样循环** —— fast 路线用解析式替代了采样，所以「加速 340 倍」 |
| `detect-gpt/paper_scripts/main.sh` | 论文本来就在**同一次实验里**跑 `--n_perturbation_list 1,10,100` 三档，不是重复多轮 |
| `detect-gpt/paper_scripts/n_perturb.sh` | 收敛实验测到 **1000**（`1,10,100,1000`，n_samples=100）|
| `detect-gpt/run.py` 默认值 | `--n_perturbation_list "1,10"` |

**结论**：k 只属于 detectgpt 的掩码扰动，且论文一次跑 1/10/100 三档对照即可，
**已并入上面第 1 项**，不再单列。同时纠正旧记录里「慢 10~20 倍」的估算 ——
那是对 fast 路线的误推。

### 耗时估算的三次纠正（实测数据）

| 说法 | 出处 | 实际 |
|---|---|---|
| 单条 13.6 秒 / 139.9 秒（→ 全量 80 小时）| 早期记录 | ❌ 那是**带采样**的旧配置 |
| ~25 分钟/轮、慢 10~20 倍 | 旧待办 | ❌ 对 fast 路线不适用（无 k）|
| 全量 21,200 条，单条 1.1 秒，合计 6.3 小时 | 2026-09-24 第一次实跑 | ✅ 方向对，但单条耗时本身有波动 |
| **中 1.01 秒 / 英 0.65 秒 → 4.3h + 1.1h = 5.4 小时** | **2026-09-24 第二次实跑（用户全程观察进度条）** | ✅ 英文侧快于第一次；两次取保守值仍是 **6 小时量级** |

### 已复现并定位：进度条被 print 打断（2026-09-24）

第二次标速按用户要求投到外部窗口、由用户**全程观察**，复现出真问题：

| 现象 | 根因 |
|---|---|
| 5 条跑完 5 步，进度条**停在 `1/5 = 20%`** 再也不动，明细却全打出来了（用户截图确认）| ① 循环内用 `print` 输出明细，与 tqdm 抢同一行，把进度条挤停；② **每次只传 1 条文本**调用引擎时，`progress_cb` 的 `done` 每次都从 1 重来，`bar.update(done - last)` 第二次起等于 `update(0)`，只走了 1 步 |

**修法**（已写入 skill 的进度条条目，避免再犯）：

- 进度条活跃期间输出一律用 `tqdm.write()` / `bar.write()`，**禁用 `print`**
- 逐条调用时**每次调用前重置 `last = 0`**（或改用 `bar.update(1)`）；
  整批一次调用不存在此问题 —— 这也是「不要自己分块」的原因之一

**影响**：只影响长任务的可观测性，不动主线功能、不改变产出结果。
脚本已按上述两点修好（`%TEMP%\aigc_fast_speed.py`），供后续标定器起步。

### 静态检查告警的处理（2026-09-23 记录，2026-09-24 完成）

删掉 `pyrightconfig.json` 后裸跑 `pyright` 会报 **449 errors**。逐类看过，
**约 370 条不是代码问题，是检查器不了解本项目**：

| 类别 | 数量 | 性质 | 处置 |
|---|---|---|---|
| `Import "core.*" could not be resolved` | ~100 | 运行时由 `sys.path.insert` 注入 `app/`，静态看不到 | `extraPaths` 覆盖两个导入根（**必须保留**）|
| `Cannot access attribute "Yes"/"UserRole"/"Horizontal" for class "type[Qt]"` | ~50 | `Qt` 是枚举容器，PySide6 stub 不全 | 检查器误判，关 `reportAttributeAccessIssue` |
| `Argument of type "str \| None" ... "title" of type "str"` | ~60 | `tr()` 返回注解缺失（实际永不为 None）| `tr()` 已能推断为 `str`，**关闭该类已不再必要** ✅ |
| `int` cannot be assigned to `pack_configure` | ~40 | `installer.py` 的 tkinter 调用误判 | 检查器局限，关 `reportArgumentType` |
| `reportOptionalSubscript` / `reportOptionalOperand`（`None` 参与运算）| ~80 | ⚠️ 可能含真 bug | **本次逐条查完**，见下 ✅ |
| `predict_paragraphs` 重写不兼容 | 4 | 项目设计如此（子类用 `**kwargs`）| 关 `reportIncompatibleMethodOverride` |

**2026-09-24 的清理结果**

1. `tr()` 的返回注解 —— 复查后**不需要改**：`EN` / `ZH` 是字面量 dict，
   `table.get(key, key)` 的两条返回路径都是 `str`，`--verifytypes` 级别的证据
   是 `reportArgumentType` 关掉后仍 0 error；当年那 ~60 条的根因是
   `reportArgumentType` 那一大类，**已随该类关闭而消失**，不是 `tr()` 的问题。
2. `reportOptionalXxx` 那 ~80 条**逐条查完，无真 bug**：全部集中在
   `installer/` 的 `os.environ.get(...)`、`ui/*.py` 的 `self.parent()`、
   `engine.last_buckets` 等「运行期必非 None、静态看不出来」的位置
   （如 `build_report(buckets=None)` 的默认值、`cluster` 里先判空再取值）。
   故保留关闭状态；**若要重开，须同时给这些位置加 `# pyright: ignore[...]`
   并注释原因**，否则会立刻回到几十条噪声。
3. `base.py::_encode_capped` 里多余的 `import torch` 删掉（本方法只用
   `tok()` 返回值，不引用 `torch`）；`engines/__init__.py` 的 5 条对外接口
   导入加**单行** `# pyright: ignore[reportUnusedImport]`。

**现状**：`npx --yes pyright` = **0 errors, 0 warnings**（此前 6 条 warning）。

**注意**：做不到"改代码让 449 条全消失" —— 约 370 条源于检查器局限
（PySide6 stub、运行时路径注入、tkinter 误判），不是代码缺陷。

**已确认不做**：换论文的 Falcon-7B 打分模型 / 抓论文数据集（理由见 §1、§2.5）；
改原作者文档；工程清理中的行长与编码声明。

**已完成（不再挂待办）**：

| 事项 | 结论 |
|---|---|
| 阈值是否收敛 | ✅ **留出集验证通过**：标定集 0.8615 / 留出集 0.8673（落差 −0.58 点，**无过拟合**）|
| 划留出集 | ✅ `tools/probes/holdout.py`（按**问题**拆分防泄漏）|
| **`binoculars` 英文重标** | ✅ 0.615 → **0.8152**（旧值 FNR 0.998，几乎抓不出 AI）|
| **gltr 中英重标** | ✅ 英文 (12,25) → **(8.69, 25.64)**；中文 → **确认不可交付**（FNR 73%），用 `zh_perplexity` 替代 |
| **simpleai 实跑复核** | ✅ 中文 acc 0.9902 / AUC 0.9998；英文 AUC **0.4397**（低于随机）|
| **标定值全部实跑落盘** | ✅ gltr / binoculars / simpleai / zh_perplexity 均由探针写入 json（此前 4 项是抄文档）|
| **装机 / 界面 / 配置测试** | ✅ 三个探针（`package_flow` / `ui_flow` / `ui_config`），见 §6 |
| **GLTR 四档柱状图（2026-09-24）** | ✅ 每段下方「横向堆叠柱 + 同色图例数字」，见 §8 |
| **静态检查告警清理（2026-09-24）** | ✅ `pyright` = **0 errors, 0 warnings**，见 §3 |
| **真装机实测（2026-09-24）** | ✅ 实跑 `perform_install()` + 卸载，**首次证实装完读到的阈值来自标定 json**，见 §6.5 |

---

## 4. 原作者文档待修订（暂不改）

原话「待与原作者沟通后统一处理」。依据必须是实测数据。

| 文档 | 问题 |
|---|---|
| `README.md` | ① Binoculars 写「免调阈值」（**错**，需标定）② DetectGPT/Fast 公式漏 σ 归一化 ③ 「中英双语」指的是**界面语言**，不是查重语言，易混淆 ④ 「全部已实现」需更新 |
| `使用手册.md` | ① 同上「免调阈值」② 引擎列表缺语言标注 ③ 「不确定就用默认 SimpleAI」需改为**中文必须**用 SimpleAI |
| `README.en.md` | 同 README 对应项 |
| `CHANGELOG.md` | 需补 v1.2.9 |
| `engines_manifest.json` | `zh_perplexity` 原阈值 (20,45) 实测 FPR **95%**（人写全被判 AI）。已改为 (4.33, 11.55)，但**该文件属原作者，本次未动** |

---

## 5. 改动清单

| 路径 | 操作 | 说明 |
|---|---|---|
| `app/core/engines/base.py` | 改 | `avg_logprob` 改整段；`cross_perplexity`；fp16 + 显存三档 |
| `app/core/engines/binoculars_engine.py` | 改 | 公式按论文式 (3)(4) |
| `app/core/engines/curvature_engine.py` | 改 | σ 归一化；T5 截断；**条件独立采样**；补 `import math` |
| `app/core/engines/perplexity_engine.py` | 改 | 按语言分档阈值；**`method="rank"` 四档** |
| `app/core/engines/catalog.py` | 改 | 阈值外置化；加 `zh_perplexity`；补语言标签 |
| `app/core/engines/manager.py` | 改 | **加标定数据层**（`engines_calibration.json`）|
| `app/core/engines/engines_calibration.json` | **新建** | 标定值落盘，随程序分发 |
| `app/ui/*.py` | 改 | 语言标注、参数合并顺序、`hf_endpoint`、文件名转义 |
| `app/core/cluster.py` | 改 | master 绑随机端口 |
| `installer/`、`tools/` 多个 | 改/新建 | 见下 |

**新增工具**

| 工具 | 用途 |
|---|---|
| `tools/audit_probes.py` + `probes/` | 可复现探针（27 个，`--list`）|
| `tools/prepare_datasets.py` | 数据集加载（**内存处理，不落盘**）|
| `tools/export_calibration.py` | 导出标定值（`--audit` 查漏网的硬编码）|
| `tools/estimate_timing.py` | 跑全量前测单条耗时 |

**注**：`engines_manifest.json`、`settings.json` 项目根下的引擎 json 等**原作者文件未动**。

---

## 6. 本轮改动记录（2026-09-23）

### 6.1 装机 / 界面 / 配置测试（新增三个探针）

此前**从未测过**打包、装机、界面实际使用与配置合理性。

| 探针 | 覆盖 | 结果 |
|---|---|---|
| `ui_flow` | 主窗口、引擎下拉、**真跑一次检测**、设置往返、降重对话框 | ✅ 5/5 |
| `package_flow` | 装机必需文件、**标定数据位置**、installer 零依赖、卸载完整性 | ✅ 通过 |
| `ui_config` | 关键默认值、设置控件与设置项对应 | ✅ 通过 |

**四个关键验证项**：

1. **标定数据必须随安装分发** —— `engines_calibration.json` 要在 `app/` 内，
   安装器的 `copytree` 才带得上；放 `base_dir` 则全新安装后**不存在**。
2. **installer 零依赖** —— 静态核查其 import，无 torch / PySide6 / numpy / transformers。
3. **卸载完整性** —— 删注册表键 / 删快捷方式 / `rd /s /q TARGET`（含 `models/`）/
   `ping` 延迟避开文件锁，四项齐全。
4. **界面真跑检测** —— `load_file()` → 点 `btn_start` → 等 worker 启动 → 读 `result_label`
   （不是"构造一下"就算过）。

**原先"未覆盖：打包 exe（仓库无 `.spec`）"—— 2026-09-24 晚已补**：
重建 `tools/build_exe.ps1`（三步、顺序不可反），见 §8.10。这条盲区是那次
"装机装出来全是旧现象"的直接原因：源码改了，但没人重新打包。

### 6.5 真装机实测（2026-09-24 补做）

此前装机**只有静态核查**（理由：真装会写注册表 + `rmtree`）。本次在
`D:\AIGC_inst_test` 实跑 `perform_install()`，跑完把注册表项、桌面快捷方式和
目录全部清理，机器已复原。

| 环节 | 实测结果 |
|---|---|
| 下载便携包 + get-pip | ✅ 走 npmmirror，**20 秒内**完成（10.62MB + 2.13MB），zip 结构校验通过 |
| 解压 + 修补 `_pth` + 写 sitecustomize | ✅ |
| 引导 pip | ✅ `pip 26.2.1 (python 3.12)` |
| copytree 复制 `app/` | ✅ `main.py` / `first_run.py` 到位 |
| **标定数据随安装到位** | ✅ `app/core/engines/engines_calibration.json` 8 条 |
| **runtime 真能跑 app** | ✅ 用装好的 python 3.12.10 导入 `core.i18n` / `catalog` / `manager`，10 个引擎枚举成功 |
| **标定值真覆盖出厂值** | ✅ `binoculars.threshold=0.8152`、`gltr=(25.64, 8.69)`，均来自 json 而非 `catalog.py` |
| torch 未装时降级 | ✅ `TORCH_OK=False`，`TORCH_ERROR=No module named 'torch'`，引擎清单仍完整可枚举 |
| 卸载注册项 / 桌面快捷方式 | ✅ 均写入（DisplayName=AI 检测工具箱）|
| **卸载清理** | ✅ 注册表项删除、快捷方式删除、`rd /s /q` 删净安装目录，**零残留** |

**这条最关键**：静态核查只能证明「文件在 `app/` 内」，证明不了「装完能跑起来、
且读到的是标定值」。本次把后者也证实了 —— 用户装完拿到的确实是 0.8152 / 25.64 / 8.69。

同步补的说明：下载走**镜像**且带**实时百分比**（`status(msg, pct)`，见
`_fetch_urllib`），失败按「urllib → 直连 urllib → 系统 curl → 手动指定包」四级兜底。

### 6.2 静态检查（`pyrightconfig.json`）

`npx --yes pyright` 从 **391 errors → 0**，过程中查出 **3 个真问题**：

| # | 文件 | 问题 | 后果 |
|---|---|---|---|
| 1 | `k_timing.py` | 引用未定义的 `K_LIST` | 跑到汇总必崩（该探针从未跑过 —— 需 2.7B 模型）|
| 2 | `ui_flow.py` | 用了 `sys` 但未导入 | 运行必崩（去 BOM 时误删所致）|
| 3 | `static.py` / `model.py` | 6 个函数**各两份定义** | 第一份是死代码，共 160+ 行 |

**配置要点**：`extraPaths` 须覆盖**全部导入根**（本项目 2 个：`app/` 与
`app/core/`，后者供 installer 的裸模块名 `i18n` / `netfix`）；
只把 `reportRedeclaration` / `reportUndefinedVariable` 当 error。

### 6.3 GLTR 四档展示（数字版）

报告每段下方多一行：

```
第1段   AI 概率 82%   段一文本…
        绿 78% │ 黄 8% │ 红 14% │ 紫 0%
```

**接法**：`predict_paragraphs` 的 `list[float]` 约定被三处共用，故走**实例属性旁路**
（`engine.last_buckets`）；`detect_local` 一并回传引擎实例。
**调用方一行未改**（`benchmark` / `cluster` 只读 probs）。

**两个限制**：

| 限制 | 说明 |
|---|---|
| 集群模式无四档 | 分片在节点进程内算，跨节点合并需另设计协议 |
| `ppl` 路线下四档只展示 | 只有 `method="rank"` 时四档才参与判别，故**不影响任何已有阈值** |

**未做（TODO）**：柱状图 / 涂色图 —— **2026-09-24 已补，见 §8.1**。

### 6.4 顺带修的

- 四档各自 `round()` 后和可能是 99%/101%（实测 3000 例中 1014 例）→ 改**最大余数法**
- 四档文案硬编码中文 → 补 `i18n.py` 的 `ZH` / `EN`
- 全 0 四档会生成一行空 `<tr>` → 判据改用**渲染结果是否为空**

---

## 7. 探针索引（29 个）

`python tools/audit_probes.py --list` 看完整代价/风险。**safe 组默认跑，heavy 需显式指定。**
（**以 `--list` 实测为准**，本表为 2026-09-24 快照。）

| 组 | 探针 | 用途 |
|---|---|---|
| safe | `static_scan` | 未用导入 / 行长 / 静默 except / **UTF-8 BOM** |
| safe | `style_report` | 原作者风格核查 |
| safe | `xformers_sig` `bino_math` `style_loop` `license_i18n` `logprob_chunk` | API / 公式 / 死循环 / license / 分块口径 |
| safe | **`package_flow`** | 装机流程静态检查（必需文件、标定数据位置、零依赖、卸载）|
| safe | **`env_setup`** | **新增**：路径校验 / CUDA 映射 / 卸载器（独立 exe）/ 进度解析 / 启动自检 |
| safe | **`display_marks`** | **新增**：报告四档和恒为 100 / 柱状图边界 / 引擎语言标注 |
| safe | **`ui_config`** | UI 配置合理性（默认值、控件与设置项对应）|
| heavy | `cluster_port` `cluster_chain` | 集群端口与发现链路 |
| heavy | `gui_offscreen` `report_render` **`ui_flow`** | 界面构造 / 报告渲染 / **真跑一次检测** |
| heavy | `xformers_call` `dtype_compare` | transformers 真调用 / fp16 vs fp32 |
| heavy | `crosslingual` `zh_backbone` `auc_bench` | 双语对照 / 中文底座 / AUC 基准 |
| heavy | **`zh_threshold` `gltr_cal` `bino_cal` `simpleai`** | **四个阈值标定器**（结果写回 `engines_calibration.json`）|
| heavy | **`english_fpr` `holdout`** | 英文 FPR<=5% 复核 / 留出集验证（防过拟合）|
| heavy | `k_timing` `vram_spill` | 采样数 k 耗时 / 显存溢出实测 |

**注**：标定器跑完**自动写 json**，不需手工抄数字 —— 见 `AGENTS.md`「标定值必须外置」。
**装机项已升级为实测**：§6.5 真跑过 `perform_install()`，本节的 `package_flow` 保留为
日常回归（秒级、无副作用），两者互补。
**打包项同样不再靠人记**（2026-09-24 晚）：`tools/build_exe.ps1` 生成带 git 短哈希的
`build_info.json`，装完日志首行就能看出装的是哪一版 —— 见 §8.10。

---

## 8. 本轮改动记录（2026-09-24）

### 8.1 GLTR 四档柱状图

论文原产物是「逐 token 涂色 + 四档直方图」；数字版（§6.3）能读数但看不出比例，
本次补上柱状图。

```
第1段   AI 概率 82%   段一文本…
        [██████████████░░░░███─────────]   绿 78% │ 黄 8% │ 红 14% │ 紫 0%
```

| 决策 | 理由 |
|---|---|
| **横向一根 100% 宽堆叠柱**，不是竖排直方图 | 报告逐段渲染，每段一根横条不增加行高；竖排还要给坐标轴留空间 |
| **用 SVG 画**，不用 `<div>` 套色块 | 报告在 `QTextBrowser` 渲染，它只实现 HTML4 子集，`float`/flex 都不支持，横排色块会退化成竖排；SVG 是 Qt 原生支持的 |
| **颜色随占比调明度**（占比 0% 的档仍有浅色底）| 论文涂色图就是这个读法：越饱和 = 该档命中越多。可见底色保证"这一档存在但没命中" |
| **柱 + 图例数字并排** | 柱子给比例直觉，数字给精确值，两处同色一一对应；纯柱子读不出「78%」这种确切值 |
| **柱宽按 `_pct100` 的结果算** | 复用已有的「和恰为 100」保证，柱子总和必然铺满，不出现缝或溢出 |

**边界处理**（`CHECK_FLOW.md` 三）：`None` → 空串；全 0 → 空串（不出空行）；
四档之和非 100 时 `_bar_svg` 自行归一；`buckets` 短于段落数时不越界（原有判断）。

**新增 i18n**：`bucket_legend`（`ZH` / `EN`），且**只在真有四档数据时才显示** ——
非统计派引擎（simpleai 等）显示这句会让人以为数据丢了。

### 8.2 pyright 收尾

见 §3。**0 errors**；`reportUnusedImport` 剩 5 条，如实 pending。

**这 6 条 warning 的来龙去脉**（含一次返工）：

1. `base.py::_encode_capped` 里那句 `import torch` 是**真多余**（该方法只用
   `tok()` 的返回值做张量切片），**删掉**并写明原因；
2. `engines/__init__.py` 的 5 条是**有意**的（4 条对外接口导入 + 1 条
   `try: import torch` 探测导入），先按 `CHECK_FLOW.md` 第 1 层的要求加了单行
   `# pyright: ignore[reportUnusedImport]` 抑制；
3. **随后用户要求撤掉抑制、改为如实记录** —— 现在 pyright 报
   `0 errors, 5 warnings`，这 5 条进 §3 待办，不再假装零告警。

### 8.3 真装机实测

见 §6.5。**这条把「装机只做静态核查」的缺口补上了**，并且首次证实
「用户装完拿到的阈值来自标定 json」而不是出厂值。

### 8.4 原文核对与待办纠偏（2026-09-24）

arXiv MCP 报 406，按规则改用 `curl` 直连 arXiv API + GitHub MCP 对照官方仓库，
推翻了两条旧判断（详见 §3「原『k 提到 100』已撤销」）：

1. **fast 路线没有 k** —— `compute_crit()` 一次前向出解析式曲率，故「k 提到 100」对
   fastdetectgpt 不适用；它只属于 detectgpt 的掩码扰动，且论文一次跑 `1,10,100` 三档。
2. **非英语扰动模型论文用 `google/mt5-xl`**（`paper_scripts/supervised.sh`），
   不是泛指的 mT5 —— 补强了 §2.4 的结论，也给了换模型的具体档位。
3. **耗时估算纠正**：全量 21,200 条（中 15,216 + 英 5,984，来自 `load_balanced`
   的全量口径）**实测单条 1.1 秒 → 合计 6.3 小时**，不是早期记录的 80 小时。

### 8.5 未标定引擎的标注简化为一个符号（2026-09-24）

要求：**引擎可以不禁用，但必须标注让用户明白"不确定性很大"，一个符号即可。**

| 改前 | 改后 |
|---|---|
| `🌐 中文 / 英文 ❔ 未标定`（语言前缀 + 符号 + 文字）| **`❔`**（单个符号）|

列表里显示成 `❔ Fast-DetectGPT（零样本）` —— 只多一个字符，不挤掉引擎名。

| 决策 | 理由 |
|---|---|
| **顺带修正注释与代码的矛盾** | 原注释写「未标定…**单独显示，不参与中/英前缀拼接**」，代码却拼了 `🌐 中文 / 英文`。未标定即**连适用哪门语言都没测**，标语言等于编造 —— 现按注释本意只回符号 |
| 用 `❔` 而非 `⚠️` | ⚠️ 已被「有结论但弱」占用，两者语义**相反**：⚠️ 是"测出来差"，❔ 是"还没测" |
| 含义放**该行悬停提示**（`mark_tip_unmeasured`，中英各一条）| 列表列宽放不下解释；鼠标停在 `❔` 上即弹出。**只给未标定设提示** —— 其余标记自带文字（`✅ 可用`、`⚠️ 中文弱`），自解释，再加提示是冗余 |
| **引擎仍可选可跑** | 标注只负责说明"结论还没有"，不禁用 |

实测输出（`engine_lang_mark`）：`simpleai`→`🌐 中文 ✅ 可用`、`gltr`→`🌐 中文 / 英文 ⚠️ 中文勿用`、
`fastdetectgpt`→**`❔`**（长度 1）、规则/评测类→空串（不标语言）。

### 8.6 进度条教训写入 skill（2026-09-24）

用户要求「在 skill 里进度条部分加几个字，总结好这个问题以后不再犯」。已写入
`user-preferences` 的进度条条目，两条：

1. **进度条活跃期间输出一律用 `tqdm.write()`，禁用 `print`** —— `print` 与 tqdm
   抢同一行，会把进度条挤停在中途（实测 5 条跑完 5 步，停在 `1/5 = 20%`）
2. **逐条调用引擎时 `progress_cb` 的 `done` 每次从 1 重来** —— 直接
   `bar.update(done - last)` 第二次起等于 `update(0)`；每次调用前重置 `last = 0`

**同步范围**（按规则「只改真源 → 复制覆盖全部副本 → 核对哈希」）：

| 位置 | 处理 |
|---|---|
| OneDrive 真源 `SKILL.md` | 直接改 |
| `.agents` / `.claude` / `.codex` 副本 | **复制覆盖**（原副本落后真源 3146 字节，`B-other.md` 落后 250 字节，一并同步）|
| `.cline/rules/user-preferences.md` | 扁平变体、格式不同，**手工加同样两条** |

同步后 5 处均含 `tqdm.write` 与「done 每次从 1 重来」，三副本与真源 `SKILL.md`
哈希一致（`BEC4C61BED90D659`）。

### 8.7 文档同步

- 本文件 §3 待办 3 项 → **2 项**、§6.5 新增真装机实测、§7 探针快照日期改 2026-09-24；
  `AGENTS.md` 文档索引补探针数与分组说明
- 剩余待办见 §3

### 8.8 安装器 / 首次启动 / 卸载器改造（2026-09-24）

| # | 改动 | 要点 |
|---|---|---|
| 1 | **安装器加「运行环境」对话框**（只做"新建"）| 默认 `<安装目录>\\runtime\\python`，可改到别的盘；点「检测」逐条校验（非法字符／保留名／盘符／过长／危险位置／非空）；**危险位置直接拒绝**（盘根、Windows、用户主目录、桌面、Program Files）；非空目录要二次确认 |
| 2 | **卸载器改三个勾**（默认都不打）| 缓存与日志 ／ Python 运行环境 ／ 已下载模型 —— 三者**性质不同**：缓存删了零损失、环境删了要重下、模型是用户资产（10GB 的可能几小时）。模型目录可从 settings.json 外置，**只删我们自己的子目录**，不整删 |
| 3 | **CUDA 自适应** | 新建 `app/core/gpuinfo.py`（纯标准库）：读 `nvidia-smi` 的 `CUDA Version` → 映射 `cu129/cu128/cu126/cu124/cu121/cu118`；低于 11.8 或无 N 卡走 CPU 版并说明原因 |
| 4 | **装后真验 CUDA** | 装了 GPU 版但 `cuda.is_available()` 为 False（驱动过旧）→ **自动回退 CPU 版**，否则用户拿到"装了却用不了"的环境 |
| 5 | **依赖表修正** | `DEPS` 拆成 `(导入名, pip 名, 版本约束)`：`docx` → **`python-docx`**（已核实：PyPI 的 `docx` 是 2014 年的另一个库）；`transformers`/`PySide6` 加主版本上限 |
| 6 | **pip 缓存外置** | `--cache-dir <app>\\_pipcache`，装完／重开时清空 —— 不再往用户全局 `%LOCALAPPDATA%\\pip\\Cache` 塞 2~3GB |
| 7 | **失败不退出** | 弹「继续 ／ 重新开始 ／ 退出」；「重新开始」**先清干净缓存与下载**（半成品会让 pip 报怪错） |
| 8 | **启动自检 L1–L3** | 新建 `app/core/selfcheck.py`：依赖存在性 + 真 import + CUDA 可用，**实测 1.51 秒**；后台跑、有问题才弹提示（L4 真跑检测不做） |
| 9 | **真实进度条** | 分母 = pip 输出 `Downloading x (2.6 GB)` 累加；分子 = 缓存目录实际字节（0.1 秒量一次）→ 显示「已下载/总量 ｜ 已用 ｜ 剩余」。拿不到分母就**退化成只报已下载量，不编百分比** |

**实测的源清单**（2026-09-24，别再踩）：

| 源 | 结果 |
|---|---|
| 清华 `mirrors.tuna.tsinghua.edu.cn/pytorch-wheels/` | ❌ **404 已失效**（原先还是第一个源）|
| 阿里云 ／ 华为云 | ❌ 索引里**只有 Linux wheel**，Windows 不能用 |
| **上海交大** `mirror.sjtu.edu.cn/pytorch-wheels/` | ✅ 有 `win_amd64`，cu128/cu129 齐 |
| 官方 `download.pytorch.org/whl` | ✅ 兜底 |
| 清华 PyPI `/simple` | ✅ **正常**（失效的只是它的 pytorch-wheels 目录，别整片删源） |

**装机复跑时揪出的真 bug**（2026-09-24，由真装机验证 + 新建的 `env_setup` 探针联合发现）：

| 现象 | 根因 | 修法 |
|---|---|---|
| 用户自选环境路径时，卸载器里的 `RUNTIME_ROOT` 指向该路径的**父目录**；若用户选 `D:\myenv`（只一层），反推得到 `D:\` —— 卸载时 `rd /s /q` 会删到**磁盘根** | `register_uninstall` 从 `pythonw.exe` 往上反推两级 | 改由 `perform_install` **直接传入用户选定的那个环境目录**（`@RUNTIME_DIR@`）；卸载只删该目录本身，绝不碰父目录（仅当父目录恰是默认的 `<TARGET>\runtime` 时才顺手删空壳）。**2026-09-24 晚改独立 exe 后**：占位符方案取消，环境路径由安装器写进注册表 `RuntimeDir`、卸载器读它 —— 见 §8.10 |

### 8.9 改动文件（本轮全部）

| 文件 | 改动 |
|---|---|
| `app/core/report.py` | 四档柱状图（`_shade` / `_bar_svg` / `_bucket_cell`）+ 图例行 |
| `app/core/i18n.py` | `bucket_legend`、`mark_tip_unmeasured`（中英各一条）|
| `app/core/engines/base.py` | 删 `_encode_capped` 里多余的 `import torch` |
| `app/core/engines/__init__.py` | 5 条接口 / 探测导入：**pyright 抑制标记已按用户要求撤销**，改列 §3 待办 |
| `app/ui/engine_dialog.py` | 未标定标注简化为 `❔`；新增 `_UNMEASURED_MARK`；给 `❔` 行加悬停提示 |
| `app/core/gpuinfo.py` | **新建**：显卡 / CUDA 探测（纯标准库，installer 与 first_run 共用）|
| `app/core/selfcheck.py` | **新建**：启动自检 L1–L3 |
| `app/main.py` | 启动时后台自检，有问题才弹提示 |
| `app/first_run.py` | 依赖表（docx→python-docx + 版本上限）、源修正、pip 缓存外置、失败三选项重试、真实进度条 |
| `installer/installer.py` | 「运行环境」选择对话框 + 路径校验；卸载器改三个勾 |
| `tools/probes/package_flow.py` | 必需文件加 `core/gpuinfo.py` |
| `AGENTS.md` | 文档索引补探针数与分组 |
| `docs/FIXES.md` | §3 待办纠偏、§6.5 真装机、§8 本轮记录 |
| `docs/HANDOFF.md` | §3 待办、真装机结论、进度条结论 |

**项目外**（skill，按规则同步 4 个客户端副本）：

| 位置 | 改动 |
|---|---|
| OneDrive 真源 `SKILL.md` + `.agents`/`.claude`/`.codex` 副本 + `.cline/rules/user-preferences.md` | 进度条两条教训（`tqdm.write()` 禁用 `print`；`progress_cb` 逐条重置）|

**更新日期**：2026-09-24

### 8.10 卸载器 exe 化 / 打包流程重建 / 装完自关（2026-09-24 晚）

**背景**：用户按 `HANDOFF.md` 实测装机，看到的界面全是旧样（没有语言标注、没有 `❔`、默认引擎
也不对），安装器装完不关，卸载入口是 `pythonw.exe + .pyw`。查证结论 —— **装出去的是 9/19 的包**：

| 证据 | 事实 |
|---|---|
| `git log -1 -- app/first_run_gui.exe`、`-- dist/AIGC_Toolkit_Setup.exe` | 最后提交都是 `63f47ad`（**9/19**，作者那版）|
| `app/core/engines/engines_calibration.json` 首次提交 | `11edfcb`（9/24）—— 旧安装器里**根本没有**这个文件 |
| 装机的全局 pip 缓存内容 | 有 `docx-0.2.4`（2014 年错包）→ 用的是修正前的依赖表 |

**根因**：`app_source_dir()` 在打包后返回 `sys._MEIPASS/app`，即**安装器把 app 的快照打在自己里面** ——
源码改了必须重新打包，否则装出去永远是旧代码。而仓库里既没有 `.spec` 也没有打包脚本
（作者原有 `build_installer.ps1` / `.bat`，在"精简仓库" `3e162a6` 时被删），这步一直靠手工敲命令。

| # | 改动 | 要点 |
|---|---|---|
| 1 | **卸载器改独立 exe** | 新建 `installer/uninstaller.py` → `dist/uninstaller.exe` → 装机复制到 `<安装目录>\uninstaller.exe`，注册表 `UninstallString` 指向它。旧方案（生成 `.py` 交给 `pythonw`）退场：一般软件卸载入口都是 exe；`.py` 依赖运行环境，环境坏了卸载器自己也跑不起来 |
| 2 | **环境路径写进注册表** | 安装器写 `RuntimeDir`，卸载器读它（用户可能把环境放到别的盘）|
| 3 | **安装器装完自动关闭** | 成功 → 提示一次后 `destroy()`（此前只弹提示 + 复位按钮 → 用户以为没装完、还能再点一次"开始安装"）；失败才复位按钮 |
| 4 | **打包流程重建** | `tools/build_exe.ps1`：三步（uninstaller → first_run_gui → installer，**顺序不可反**）；后两者随安装器内嵌分发 |
| 5 | **构建标记（防呆）** | 打包生成 `build_info.json`（版本 + git 短哈希 + 时间，**无 BOM**），安装日志首行打印，并落到安装目录；读侧 `utf-8-sig` 兜底 |
| 6 | **探针同步** | `env_setup` 第 3 节、`package_flow` 第 5 节：核查对象从模板字符串改为 `installer/uninstaller.py`；新增「旧模板已退场 / RuntimeDir 两边一致 / 安装器复制注册 exe / 自删 `del`+`rd`」四项 |
| 7 | **旧包残留清理** | 删 `%LOCALAPPDATA%\pip\Cache`（2.915 GB，旧 exe 装的依赖缓存）与 `%TEMP%` 6 项探针残留；注册表 / 快捷方式 / PATH / 安装目录复查干净 |

**打包时踩到并修掉的两个坑**（都写进了代码注释）：
`build_info_path()` 的 `..` 写重 → 跑到仓库外读不到文件；PS 5.1 的 `Set-Content -Encoding UTF8`
写 BOM → `json.load` 抛异常、静默退化成 `dev`。

**产物**：`dist/uninstaller.exe` 11,905,769 ｜ `app/first_run_gui.exe` 11,843,441 ｜
`dist/AIGC_Toolkit_Setup.exe` 36,720,488（旧包 24,736,939，且不含 `engines_calibration.json`）。

**验证**：pyright 0 errors（5 条 warning 见 §3）、smoke 10/10、engines 13/13、
test_detect / fusion_selftest 全过、`env_setup` 与 `package_flow` 全项 OK；
`build_line()` 实测输出 `安装包：v1.3.0 ｜ 构建 1d9eb02 ｜ 2026-09-24 07:35:38`。

**未做**：用新 exe 真装一次 —— 装机端到端才是最终判据，见 §3 待办（第 4 项）。

**改动文件**

| 文件 | 操作 |
|---|---|
| `installer/uninstaller.py` | **新建**（独立卸载器）|
| `installer/installer.py` | 删 219 行模板；`register_uninstall()` 改为复制 exe + 写 `RuntimeDir`；装完自动关闭；新增 `build_info_path` / `build_stamp` / `build_line` / `uninstaller_source`；补 `import json` |
| `tools/build_exe.ps1` | **新建**（三步打包 + 构建标记）|
| `tools/probes/env_setup.py` | 第 3 节改核查 `uninstaller.py`，并加安装器/卸载器接口四项 |
| `tools/probes/package_flow.py` | 第 5 节同上（新增 4 项检查）|
| `tools/audit_probes.py` | env_setup 探针描述文案同步 |
| `app/core/i18n.py` | `inst_build_line`、`inst_uninstaller_missing`（中英各一条）|
| `app/first_run_gui.exe`、`dist/AIGC_Toolkit_Setup.exe` | 重打（产物）；新增 `dist/uninstaller.exe`（随 dist 忽略规则，不入库）|
| `docs/FIXES.md`、`docs/HANDOFF.md`、`docs/CHECK_FLOW.md`、`AGENTS.md` | 文档同步 |

**更新日期**：2026-09-24（晚）

---

## 9. GLTR 四档展示（数字版，2026-09-23）

已由 §8.1 的柱状图取代，**接口不变**（`build_report(..., buckets=...)`、
`engine.last_buckets` 旁路）。保留本节只为说明接法，免得后人重找：

- 接法：`predict_paragraphs` 的 `list[float]` 约定被三处共用，故走**实例属性旁路**
  （`engine.last_buckets`）；`detect_local` 一并回传引擎实例
- 调用方一行未改（`benchmark` / `cluster` 只读 probs）
- 集群模式仍无四档（分片在节点进程内算，跨节点合并需另设计协议）
- `ppl` 路线下四档只展示；只有 `method="rank"` 时四档才参与判别

