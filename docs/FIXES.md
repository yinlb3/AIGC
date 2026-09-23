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

**只剩 4 项**（其余均已完成或确认不做）。

| 优先级 | 事项 | 卡点 |
|---|---|---|
| 高 | **`fastdetectgpt` 中英标定** | 需可用显存 ≥7GB。**唯一没数据的主力引擎** |
| 高 | **`detectgpt` 中文换 mT5 扰动模型** | ✅ 论文给了方案（见 §2.4）。成本：下载 mT5 + 标定（单条 29 秒，上千条约 8 小时）|
| 中 | 采样数 k 提到 100（验证 σ 归一化）| 论文说 k=100 才收敛；慢 10~20 倍 |
| 低 | **GLTR 四档柱状图**（论文原产物是涂色图 + 直方图）| **数字版已做**（每段下方一行「绿 x% │ 黄 x% │ 红 x% │ 紫 x%」），柱状图未做 |
| 低 | **静态检查告警的系统性清理** | 见下 |

### 静态检查告警的处理（2026-09-23 记录）

删掉 `pyrightconfig.json` 后裸跑 `pyright` 会报 **449 errors**。逐类看过，
**约 370 条不是代码问题，是检查器不了解本项目**：

| 类别 | 数量 | 性质 |
|---|---|---|
| `Import "core.*" could not be resolved` | ~100 | 运行时由 `sys.path.insert` 注入 `app/`，静态看不到 → **只能靠配置** |
| `Cannot access attribute "Yes"/"UserRole"/"Horizontal" for class "type[Qt]"` | ~50 | `Qt` 是枚举容器，PySide6 stub 不全 → **检查器误判** |
| `Argument of type "str \| None" ... "title" of type "str"` | ~60 | `tr()` 的返回注解没写准（实际永不为 None）→ **可修**：给 `tr()` 加返回类型 |
| `int` cannot be assigned to `pack_configure` | ~40 | `installer.py` 的 tkinter 调用误判 → 检查器局限 |
| **`reportOptionalSubscript` / `reportOptionalOperand`**（`None` 参与运算）| ~80 | ⚠️ **可能含真 bug** —— 如 `catalog.by_id()` 返回 `Optional` 后直接 `.get()`（已在 `static.py` 修过 2 处）|
| `predict_paragraphs` 重写不兼容 | 4 | 项目设计如此（子类用 `**kwargs`）|

**当前处置**：`pyrightconfig.json` 保留 `extraPaths`（**必须**，否则 100 条假错报）；
但 `reportOptionalXxx` 那批**是直接关掉的，属掩耳盗铃** —— 里面混着可能的真 bug。

**待办**：

1. **修 `tr()` 的返回注解** → 消掉 ~60 条（真改进）
2. **把 `reportOptionalXxx` 打开**，逐条查那 ~80 条，真 bug 修掉、
   设计使然的加 `# pyright: ignore[...]` 并注释原因
3. **不要一次性全关** —— 那是把可能的真问题一起关掉

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
| **GLTR 四档展示（数字版）** | ✅ 每段下方显示「绿 78% │ 黄 8% │ 红 14% │ 紫 0%」，见 §9 |

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
| `tools/audit_probes.py` + `probes/` | 可复现探针（`--list`）|
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

**未覆盖**：打包 exe（仓库无 `.spec`）、真装机（会写注册表 + `rmtree`，改静态核查）。

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

**未做（TODO）**：柱状图 / 涂色图（论文原产物）。

### 6.4 顺带修的

- 四档各自 `round()` 后和可能是 99%/101%（实测 3000 例中 1014 例）→ 改**最大余数法**
- 四档文案硬编码中文 → 补 `i18n.py` 的 `ZH` / `EN`
- 全 0 四档会生成一行空 `<tr>` → 判据改用**渲染结果是否为空**

---

## 7. 探针索引（27 个）

`python tools/audit_probes.py --list` 看完整代价/风险。**safe 组默认跑，heavy 需显式指定。**
（**以 `--list` 实测为准**，本表为 2026-09-23 快照。）

| 组 | 探针 | 用途 |
|---|---|---|
| safe | `static_scan` | 未用导入 / 行长 / 静默 except / **UTF-8 BOM** |
| safe | `style_report` | 原作者风格核查 |
| safe | `xformers_sig` `bino_math` `style_loop` `license_i18n` `logprob_chunk` | API / 公式 / 死循环 / license / 分块口径 |
| safe | **`package_flow`** | 装机流程静态检查（必需文件、标定数据位置、零依赖、卸载）|
| safe | **`ui_config`** | UI 配置合理性（默认值、控件与设置项对应）|
| heavy | `cluster_port` `cluster_chain` | 集群端口与发现链路 |
| heavy | `gui_offscreen` `report_render` **`ui_flow`** | 界面构造 / 报告渲染 / **真跑一次检测** |
| heavy | `xformers_call` `dtype_compare` | transformers 真调用 / fp16 vs fp32 |
| heavy | `crosslingual` `zh_backbone` `auc_bench` | 双语对照 / 中文底座 / AUC 基准 |
| heavy | **`zh_threshold` `gltr_cal` `bino_cal` `simpleai`** | **四个阈值标定器**（结果写回 `engines_calibration.json`）|
| heavy | **`english_fpr` `holdout`** | 英文 FPR<=5% 复核 / 留出集验证（防过拟合）|
| heavy | `k_timing` `vram_spill` | 采样数 k 耗时 / 显存溢出实测 |

**注**：标定器跑完**自动写 json**，不需手工抄数字 —— 见 `AGENTS.md`「标定值必须外置」。
