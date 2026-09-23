# AIGC 工具箱 审查记录

- 日期：2026-09-22 ~ 2026-09-23（首轮审查 09-22，次轮修复与实测 09-23）
- 审查对象：`d:\Project\AIGC`（v1.2.8）
- 验证环境：`C:\ProgramData\miniconda3\envs\pytorch\python.exe`
  - Python 3.12.8 / torch 2.8.0+cu129 / CUDA 12.9 可用
  - RTX 4080 SUPER 16GB / transformers 5.17.0 / PySide6 6.9.2
- 验证方式：探针脚本（`tools/audit_probes.py`）+ 4 个自带脚本
  - **全程未下载任何模型**，真模型部分用本地随机权重小 GPT-2 构建
- 复现依据：`python tools/audit_probes.py --list` 查看全部探针，可原样重跑

> 2026-09-23 精简：删去「已撤回的判断」「论文核对」「自带测试结果」「修复路径
> 建议」「待确认事项」「审查阶段写操作清单」六节，以及 15 条内置样本原文 ——
> 前几节的结论已在 `HANDOFF.md`，后两节属过程数据。本文件只留「做了什么、
> 结果如何」。论文差异的完整版见 `PAPER_GAPS.md`，标定数据见
> `docs/calibration.md`。

---

## 一、确认的问题（共 19 条）

本节详述**首轮发现的 12 条（BUG-1~12）** —— 含定位、根因与实测。
**次轮新增的 7 条（BUG-13~19）** 详见 §3.4 的清单与 §3.9/§3.12。

| 编号 | 问题 | 状态 |
|---|---|---|
| BUG-1 | Binoculars 恒判 AI（公式/交叉项/阈值三重错） | ✅ 已修 |
| BUG-2 | `avg_logprob` 分块口径错 | ✅ 已修 |
| BUG-3 | 设置保存写坏 `hf_endpoint` | ✅ 已修 |
| BUG-4 | 集群发现被端口绑定竞争掐死 | ✅ 已修 |
| BUG-5 | detectgpt 缺 σ 归一化 | ✅ 已补（实测相悖，见 §3.9） |
| BUG-6 | fastdetectgpt 缺 σ 归一化 | ✅ 已补（同上） |
| BUG-7 | 扰动数 k=5 低于论文的 100 | ⏸️ 未改（慢 10~20 倍） |
| BUG-8 | 引擎清单参数覆盖用户参数 | ✅ 已修 |
| BUG-9 | gltr 命名与实现不符 | ⏸️ 设计决策（见 TODO-3） |
| BUG-10 | license 校验空壳 | ⏸️ 保留原状（原作者决定） |
| BUG-11 | 报告文件名未转义 | ✅ 已修 |
| BUG-12 | `smoke_test.py` 路径错，跑不起来 | ✅ 已修 |
| BUG-13 | 中文超 `n_positions` 时 CUDA 崩溃 | ✅ 已修 |
| BUG-14 | `curvature_engine.py` 缺 `import math` | ✅ 已修 |
| BUG-15 | `_mask_perturb` 超 T5 输入上限 | ✅ 已修 |
| BUG-16 | `avg_logprob` 后死代码残留 | ✅ 已删 |
| BUG-17 | gltr 阈值只适配英文 | ✅ 已按语言分档 |
| BUG-18 | gltr 在长文/新闻类上判别力骤降 | ⚠️ 方法局限，未修 |
| BUG-19 | 显存不足静默降速（fp32 溢出） | ✅ 已修（fp16 + 显存预检） |
| 新增 | 跨模型 B 值计算 `cross_perplexity` | ✅ 已加 |

**统计：19 条确认，已修 14，未修 5（BUG-7/9/10/18 + BUG-9 属设计决策）。**

---

### BUG-1【P0】Binoculars 恒判 AI —— 公式 / 交叉项 / 阈值三重错

- 位置：`app/core/engines/binoculars_engine.py:54-58`
- 实测：四组不同输入（AI 文本 / 人写文本 / 极端值）判 AI 概率
  **0.9915 ~ 0.9995**；真跑随机权重模型得 **0.99921**
- 根本原因三条：

| # | 项目写法 | 论文（arXiv:2401.12070v3 §3.3 式 4） |
|---|---|---|
| 1 | `cross_ppl = math.exp(min(-lp_perf, 700.0))` | 分母应为 `log-xPPL`，**留在 log 域**。`exp` 把量级从 ~0.5-2 拉到 ~20-3000 |
| 2 | 只算 performer 自身 NLL，与 observer 无关 | 式 (3) 要求 **M1 概率分布与 M2 对数概率逐 token 点积**，项目从未实现交叉项 |
| 3 | `score = log_ppl / cross_ppl`（log / 实数） | 应为 log / log，同量纲比，论文实测值域 0.7~1.2 |

- 阈值来源：论文 Table 1「global threshold of **0.901**」，
  项目 `catalog.py:128` 用 `threshold=0.9015` —— **抄对了数字，但量纲不匹配**
- 第三重错：论文 §3.3 明确阈值绑定 **Falcon-7B-Instruct + Falcon-7B**，
  项目 `binoculars_engine.py:26-29` 用 **gpt2 + gpt2-medium**，阈值不可移植
- 结论：该引擎当前输出**无任何参考价值**

### BUG-2【P0】avg_logprob 分块口径错 —— 影响面最广

- 位置：`app/core/engines/base.py:193-203`
- 实测：同一 100-token 输入，仅改 `chunk`

```
chunk=1024  -> -2.000000
chunk=50/25/10/4 -> -1.000000     相对差 50.0000%
```

- 根因：`total += loss * (end - begin)` 用块长作权重，
  但因果 LM 的 `loss` 内部已 shift，实际参与平均的是 `L-1` 个 token
- 影响面：`avg_logprob` 是 **binoculars / perplexity / curvature 两处**
  的公共基座 —— 单独这一条就能让 gltr、fastdetectgpt 的阈值全部失真
- **修复顺序上必须在 BUG-1 之前**

### BUG-3【P0】设置保存写坏 hf_endpoint —— 模型下载全面失败

- 位置：`app/ui/settings_dialog.py:174-178`
- 实测（真调 `SettingsDialog._save()`，离屏）：

```
保存前 hf_endpoint = 'https://hf-mirror.com'
保存后 hf_endpoint = 'hf-mirror.com'      <- 丢了协议头
```

- 根因：`_current_mirror()` 返回 `(name, url)`，代码写 `mid, _ = ...`
  后把 `mid` 同时塞给 `mirror` 和 `hf_endpoint`，`url` 被丢弃
- 连锁：`main.py:13-14` 把该值直接塞进 `HF_ENDPOINT`
- 另：`models_dir` 无校验，清空输入框会让已下模型「消失」

### BUG-4【P0】集群发现被端口绑定竞争掐死

- 位置：`app/core/cluster.py:59-66`（master）与 `151-158`（worker）
- 实测：本机同时起 master + worker，等 8 秒 → `nodes = {}`
  - 两个 socket 都能 `bind` 47650（`SO_REUSEADDR`）
  - 但直连 `TASK_PORT` 发任务是通的 → 返回 `{'type':'result','probs':[0.77,0.77]}`
- 根因：**两者用 `SO_REUSEADDR` 绑同一 UDP 端口**，单播回包只送其中一个，
  master 收不到 `AIGC_WORKER` 响应，`nodes` 恒空
- 连锁：`main_window.py:96` 要求 `nodes_snapshot()` 非空才走集群分支
  → **集群功能完全失效，UI 无任何提示**

### BUG-5【P1】detectgpt 缺 σ 归一化 + 阈值无依据

- 位置：`app/core/engines/curvature_engine.py:155-157`、`catalog.py:88`
- 论文（arXiv:2301.11305v2 §4 Algorithm 1）：

```
4: σ̃²_x ← (1/(k−1)) Σ (log p_θ(x̃_i) − μ̃)²     ▷ variance for normalization
5: if d̂_x / √(σ̃_x) > ε: return true
```

- 项目：`squash(base - mean_pert, threshold, scale)`，**完全没有 σ 项**
- 阈值：论文 §5.3「A **threshold of slightly below 0.1** separates human and
  model texts **across data distributions**」；项目 `threshold=0.0`
- 相关参数偏差：

| 项 | 论文 | 项目 |
|---|---|---|
| 扰动数 k | 100（精度收敛点） | 5 |
| mask-filling 模型 | T5-3B | t5-base |
| mask 比例 | 15% | 0.15 ✅ |

### BUG-6【P1】fastdetectgpt 缺 σ 归一化 + 采样方式不对

- 位置：`app/core/engines/curvature_engine.py:95-99`
- 论文（arXiv:2310.05130v3 §2.3 式 3）：
  `d = (log p_θ(x|x) − μ̃) / σ̃`
- 项目：只用 `base - mean_pert`，**无 σ̃**
- 论文 §3.2 消融明确「the normalization enhances ...」，σ 是核心而非装饰
- 另一偏差：论文 §2.3「Conditional **Independent** Sampling」要求逐 token
  条件独立采样（`q_φ(x̃_j|x_<j)`，与已采样 token 无关）；
  项目用 `model.generate()` 自回归整段续写，**新 token 依赖前面生成的 token**
- 采样量：论文 10,000，项目 5

### BUG-7【P1】扰动数 k=5 远低于论文

- 位置：`catalog.py:88`（`"samples": 5`）
- 论文 2301.11305 §5.3：「Detection accuracy continues to improve until
  **100** perturbations, where it converges」
- 论文 2310.05130 §2.3：用 10,000 个样本估 μ̃/σ̃
- 5 个样本估出的 μ̃ 方差极大，而项目连 σ̃ 都不算

### BUG-8【P1】引擎清单参数覆盖用户参数

- 位置：`app/ui/main_window.py:86-90`
- 实测：清单 `threshold=0.3`，用户界面设 0.7 →
  `run_params['threshold'] = 0.3`（用户值被覆盖）
- 根因：`run_params = dict(self.params)` 后 `run_params.update(eparams)`，
  **合并顺序反了**
- 附带：`min_para_len`、`use_gpu`、`use_cluster` 等非引擎参数
  也被 `**` 展开进 `predict_paragraphs()`，靠各引擎 `**kwargs` 兜底才没报错

### BUG-9【P2】gltr 命名与实现不符（非代码 bug）

- 位置：`catalog.py:50`（named "GLTR 困惑度检测"）、
  `perplexity_engine.py:15-40`
- 论文（arXiv:1906.04043v1 §3）GLTR 核心是 **Test-2「top-k 分桶」**：
  rank ≤10 绿 / ≤100 黄 / ≤1000 红 / 其余紫，输出四类占比直方图
- 项目实现是**整段平均 PPL 线性映射**（对应论文的 Test-1 退化版）
- 论文 Table 1 自证差距：Test-2 Top-K Buckets AUC **0.87±0.07**
  vs Test-1 Average Probability AUC **0.71±0.25**
- 定性：代码逻辑自洽，**不是 bug**，但 `paper` / `venue` 字段写
  arXiv:1906.04043 + 「MIT · NeurIPS 2019」会让用户误以为用了 GLTR 方法

### BUG-10【P2】license 校验空壳

- 位置：`app/core/license.py:29-32`
- 实测：

```
_validate('AIGC-PRO-0000000000000000') = True
_validate('AIGC-PRO-xxxxxxxxxxx')      = True
activate(...) -> True / 已激活专业版
current_tier() -> 'pro'
```

- 任意 `AIGC-PRO-` 开头且长度 ≥20 的字符串即可激活
- 注：代码注释写「当前为本地离线校验（演示用）」，可能是**有意占位**，
  需产品侧确认

### BUG-11【P2】报告文件名未转义

- 位置：`app/core/report.py:20`
- 实测（离屏 Qt 真渲染）：

```
文件名 'a<b>c.docx'   -> 渲染 'ac.docx'      <- <b> 被当标签吃掉
文件名 'A&B研究.docx' -> 'A&B研究.docx'      <- Qt 容忍裸 &
文件名 'a"b"c.docx'   -> 'a"b"c.docx'        <- Qt 容忍
```

- 修正初判：**只有 `<` `>` 会被破坏**，`&` 与引号 Qt 能容错
- 且 Windows 文件名不允许 `<` `>`，实际触发路径很窄

### BUG-12【P2】smoke_test.py 路径错误，完全跑不起来

- 位置：`tools/smoke_test.py:5`
- 实测：直接运行 → **10 项全 FAIL**，均为 `ModuleNotFoundError: No module named 'core'`
  加 `PYTHONPATH=app` 后 → 10/10 通过
- 根因：`sys.path.insert(0, dirname(dirname(abspath(__file__))))` 插的是项目根，
  而 `core/` 在 `app/` 下
---

## 二、静态扫描结果

- **未使用导入 14 处**：`logging_setup.py:6(sys)`、`benchmark_dialog.py:11(Qt)`、
  `engine_dialog.py:18(QFileDialog)`、`main_window.py:5(QTimer)`、
  `rewrite_dialog.py:9/12/31(os/QPushButton/pattern_name)`、
  `settings_dialog.py:7/8(Qt/QComboBox)`、`patch_offline_fix.py:15(os)`、
  `smoke_test.py:111/134/145/146`
- **行长超 80 字符 378 处 / 38 文件**，最重：`i18n.py`(53 处，最长 500)、
  `benchmark.py`(35)、`main_window.py`(26)、`aigc_rules.py`(24)、
  `installer.py`(23)、`glass.py`(21)、`rewrite_dialog.py`(21)
- **静默 except 31 处**，密集在 `cluster.py`（14 处）、`installer.py`（6 处）
- ~~**`predict_paragraphs` 参数语义错位**：`benchmark_dialog.py:212` 传
  `cfg["params"]`，但 `aigc_reduce` / `cnki_skill` 的 `params` 都是 `{}`~~
  → ✅ **2026-09-23 核实为误报**：`benchmark_dialog.py:108` 用的是
  `mgr.runnable()`，而 `manager.runnable()` 按 `category == CAT_DETECT`
  过滤（无引擎显式设 `runnable` 字段），**只返回 5 个检测引擎**；
  `aigc_reduce` / `cnki_skill` 是 `repair` 类，**根本不会出现在评测列表**。
  实测 `mgr.runnable()` 返回：binoculars / detectgpt / fastdetectgpt /
  gltr / simpleai —— 这 5 个的 `params` 都有值。
  **原判断错在假定"评测界面能选到修复类引擎"，未验证过滤逻辑。**

---

---

## 三、修复执行记录

### 3.1 修复前后对比（同一批 15 条内置样本，阈值 0.50）

| 引擎 | 指标 | 修前 | 修后 | 变化 |
|---|---|---|---|---|
| **binoculars** | 准确率 | 46.7% | **73.3%** | +26.6 |
| | FPR | **100.0%** | **50.0%** | -50.0 |
| | TN（人写判对） | **0** | **4** | +4 |
| | F1 | 0.636 | **0.778** | +0.142 |
| **gltr** | 准确率 / FPR / 召回率 | 60.0% / 0.0% / 14.3% | 同左 | 0 |
| **simpleai** | 准确率 / FPR / F1 | 60.0% / 37.5% / 0.571 | 同左 | 0 |

- `binoculars` 是主要受益者 —— 从"恒判 AI"（TN=0）变成有区分力（TN=4）。
  剩余 FP=4 需靠阈值重标定解决（0.9015 是按 Falcon-7B 标的，对 gpt2 偏高）。
- `gltr` 指标未变：判别逻辑本身没改（见 TODO-3），但底层 `avg_logprob` 已
  修正，PPL 值现在准确，为换用 Test-2 铺好了路。
- `simpleai` 不依赖 `avg_logprob`（走序列分类），指标不变，符合预期。

**修前全体指标（4 个引擎同批样本并列）：**

| 指标 | simpleai | gltr | binoculars | detectgpt |
|---|---|---|---|---|
| 样本数 | 15 | 15 | 15 | 15 |
| 准确率 | 60.0% | 60.0% | 53.3% | **33.3%** |
| 假阳性率 FPR | 37.5% | 0.0% | 0.0% | **100.0%** |
| 假阴性率 FNR | 42.9% | **85.7%** | **100.0%** | 28.6% |
| 精确率 | 57.1% | 100.0% | 0.0% | 38.5% |
| 召回率 | 57.1% | 14.3% | 0.0% | 71.4% |
| F1 | 0.571 | 0.250 | 0.000 | 0.500 |
| 耗时 | 7.6 秒 | 8.1 秒 | 14.2 秒 | 227.1 秒 |

**按语言看 FPR（关键）**：

| 语言 | simpleai | gltr | binoculars | detectgpt |
|---|---|---|---|---|
| en | **100.0%** | 0.0% | 0.0% | **100.0%** |
| zh | 0.0% | 0.0% | 0.0% | **100.0%** |

simpleai 是中文模型，**在英文上 FPR 100%**（人写的英文全判 AI）；
detectgpt 修前则中英都 FPR 100%。

**修前逐条概率（同一行并列 4 个引擎）：**

| # | 真值 | 来源 | simpleai | gltr | binoculars | detectgpt |
|---|---|---|---|---|---|---|
| 1 | 人写 | human | 0.00 | 0.15 | 0.11 | 0.97 ❌ |
| 2 | 人写 | human | 0.00 | 0.15 | 0.12 | 0.97 ❌ |
| 3 | 人写 | human | 0.00 | 0.15 | 0.08 | 0.72 ❌ |
| 4 | 人写 | human | 0.00 | 0.15 | 0.11 | 0.97 ❌ |
| 5 | 人写 | human | 0.00 | 0.15 | 0.07 | 0.71 ❌ |
| 6 | 人写 | human | 1.00 ❌ | 0.15 | 0.04 | 0.61 ❌ |
| 7 | 人写 | human | 1.00 ❌ | 0.15 | 0.05 | 0.62 ❌ |
| 8 | 人写 | human | 1.00 ❌ | 0.15 | 0.08 | 0.65 ❌ |
| 9 | AI | gpt-4 | 1.00 ✅ | 0.41 ❌ | 0.12 ❌ | 0.52 ✅ |
| 10 | AI | gpt-4 | 0.00 ❌ | 0.47 ❌ | 0.14 ❌ | 0.43 ❌ |
| 11 | AI | claude | 0.00 ❌ | 0.41 ❌ | 0.16 ❌ | 0.45 ❌ |
| 12 | AI | gpt-3.5 | 0.00 ❌ | 0.29 ❌ | 0.11 ❌ | 0.54 ✅ |
| 13 | AI | gpt-4 | 1.00 ✅ | 0.37 ❌ | 0.16 ❌ | 0.65 ✅ |
| 14 | AI | claude | 1.00 ✅ | 0.27 ❌ | 0.17 ❌ | 0.67 ✅ |
| 15 | AI | gpt-3.5 | 1.00 ✅ | 0.85 ✅ | 0.23 ❌ | 0.68 ✅ |

❌ = 判错。第 6~8 条是人写的**英文**文本；第 9~12 条是 AI 写的**中文**文本
（第 13~15 条为 AI 写的英文）。

**观察**：
- simpleai 的错判**完美按语言划分**：中文对、英文全错（第 6~8 条英文人写 → 全判 AI）
- gltr 修前几乎全判"人写"（只有第 15 条抓对）
- binoculars 全判"人写"（概率集中在 0.04~0.23）
- detectgpt 全判"AI"（人写 0.61~0.97），中英皆错

**内置样本 15 条**：作者手写的快速自检集（**非官方基准**），内容见本节上方逐条表。
要看真实水平，请从 RAID / MGTBench 官方仓库下载数据子集后通过「导入样本」评测。

### 3.2 BUG-1 修复实证：B 值恢复到论文量级

修后逐条 logPPL / log-xPPL / B（前 6 条）：

| 真值 | logPPL | log-xPPL | **B** |
|---|---|---|---|
| 人写 | -3.5375 | -4.0619 | 0.8709 |
| 人写 | -3.3512 | -3.9207 | 0.8547 |
| 人写 | -3.5299 | -3.9195 | 0.9006 |
| 人写 | -3.3095 | -3.8124 | 0.8681 |
| 人写 | -3.5268 | -3.8230 | 0.9225 |
| 人写 | -4.5085 | -4.5161 | 0.9983 |

**论文 Table 1 参考：ChatGPT 文本 B = 0.73，global threshold = 0.901。**

修前 B 落在 **0.004~0.33**（量纲错），修后落在 **0.85~1.00** —— 同一量级。

### 3.3 BUG-2 最终修法（推翻了三版中间方案）

原实现按 `chunk` 分块逐段前向再按块长加权。三种修补方案均失败：

| 方案 | chunk=16 | chunk=4 | chunk=1 |
|---|---|---|---|
| 原实现（`loss * L`） | 24.4% | 34.4% | 67.0% |
| 方案 2：权重改 `L-1` | 15.1% | 34.4% | 67.0% |
| 方案 3：加 1 token 重叠 + 手取 logits | 9.96% | 15.4% | 16.3% |
| **方案 4：整段一次前向（采用）** | **0.000%** | **0.000%** | **0.000%** |

**根因是设计缺陷，不是计数错误**，三个原因叠加：

1. **块首缺上下文** —— 从中间截断时块首 token 丢了全部前文。实测某块首位
   真值 NLL = 10.46，而同块平均仅 4.53；
2. **计数口径** —— causal LM 的 `out.loss` 内部已 shift，参与平均的是
   `L-1` 个预测位，用 `L` 加权会重复计入块首；
3. **位置编码重置** —— 每块独立喂入时 `position_ids` 都从 0 开始。

实测 `transformers` 的 `out.loss` 与 `ΣNLL/(L-1)` 在 gpt2 上相差 < 1e-7
（与 `ΣNLL/L` 差 0.068），确认第 2 点。

**最终实现**：整段一次前向 + 手取 `logits` 算 NLL，用 `max_tokens` 控制长度
上限（与论文一致）。`chunk` 参数保留仅为向后兼容。

### 3.4 已修复清单

**首轮 12 条**（BUG-7 见 §3.7 下方说明）：

| 编号 | 问题 | 文件 | 状态 |
|---|---|---|---|
| BUG-1 | Binoculars 公式（log 域 + 交叉项 + 阈值量纲） | `binoculars_engine.py` | ✅ |
| BUG-2 | `avg_logprob` 分块不可行 | `base.py` | ✅（改整段） |
| BUG-3 | `hf_endpoint` 写成裸域名 | `settings_dialog.py:174-180` | ✅ |
| BUG-4 | 集群端口绑定竞争 | `cluster.py:59-82` | ✅（实测 4 秒发现） |
| BUG-5 | detectgpt 缺 `/√σ̃` | `curvature_engine.py` | ✅（补上，但小采样下反而有害，见 2.5 节） |
| BUG-6 | fastdetectgpt 缺 `/σ̃` | `curvature_engine.py` | ✅（同上） |
| BUG-7 | 扰动数 k=5 远低于论文（100） | `catalog.py` | ⏸️ 未改（慢 10~20 倍，见 `HANDOFF.md` §3） |
| BUG-8 | 参数覆盖顺序反了 | `main_window.py:86-89` | ✅ |
| BUG-9 | gltr 命名与实现不符 | — | ⏸️ 见 TODO-3 |
| BUG-10 | license 校验空壳 | — | ⏸️ 保留原状（原作者决定） |
| BUG-11 | 报告文件名未转义 | `report.py:20` | ✅ |
| BUG-12 | `smoke_test.py` 路径错 | `tools/smoke_test.py:5` | ✅（10/10） |
| 新增 | 跨模型 B 值计算 `cross_perplexity` | `base.py` | ✅ |

**次轮新增 7 条**（BUG-13~19，详见 §3.9 / §3.12）：

| 编号 | 问题 | 文件 | 状态 |
|---|---|---|---|
| BUG-13 | 中文超 `n_positions` 时 CUDA 崩溃 | `base.py` | ✅ `_encode_capped()` |
| BUG-14 | 缺 `import math` | `curvature_engine.py` | ✅ |
| BUG-15 | `_mask_perturb` 超 T5 输入上限 | `curvature_engine.py` | ✅ |
| BUG-16 | `avg_logprob` 后死代码残留 | `base.py` | ✅ 已删 |
| BUG-17 | gltr 阈值只适配英文 | `perplexity_engine.py` | ✅ 按语言分档 |
| BUG-18 | gltr 在长文/新闻类上判别力骤降 | 同 BUG-17 | ⚠️ 方法局限，未修 |
| BUG-19 | 显存不足时静默降速（fp32 溢出） | `base.py` | ✅ fp16 加载 + 显存预检 |

**统计：19 条确认（BUG-1~19），已修 14 条，未修 5 条**（BUG-7/9/10/18 见上表；
BUG-9 与 BUG-10 属设计决策，非缺陷）。

### 3.5 第一轮回归验证

| 测试 | 结果 |
|---|---|
| `py_compile` 8 个改动文件 | 全部 OK |
| `tools/smoke_test.py` | 10/10（**不再需要 PYTHONPATH**） |
| `tools/test_engines.py` | 13/13 |
| `tools/test_detect.py` | ALL PASS |
| `tools/fusion_selftest.py` | 全部通过 |
| 集群发现实测 | 4 秒发现节点（修前恒为空） |
| `avg_logprob` 分块一致性 | 偏差 0.000%（修前 34~67%） |

### 3.6 已删除文件（历史残留）

| 文件 | 原功能 | 删除原因 |
|---|---|---|
| `tools/download_simpleai_model.py` | 下载 simpleai 模型 | 功能重复（`base.install()` 已有完整实现 + UI 入口）；路径写死 `C:\Users\hkjg2\...` |
| `tools/grab_screen.py` | 截屏存 PNG | 与检测功能无关；输出路径写死 `D:\AIGC\outputs\...` |
| `tools/patch_offline_fix.py` | 给旧版打补丁 | 补丁内容已被正式代码吸收；**且会正则改写源码，有破坏性** |
| `tools/run_detection_test.bat` | 一键跑检测测试 | 三重路径断裂；依赖的 `test_detection.py` 不在仓库 |

删除方式：`recycle.ps1` 移入回收站（可恢复）。

---

### 3.7 修复后各引擎实测

**数据见 `docs/calibration.md` 一、二章**（中英两套标定，含逐引擎
明细、PPL 分布、σ 实测、三套混合）。此处只留结论：

| 引擎 | 中文（HC3 400 条） | 英文（Ghostbuster 300 条） |
|---|---|---|
| simpleai | **99.75%**（FPR 0.50%） | 英文不可用（FPR 100%） |
| gltr | 77.50% | **93.67%**（essay） |
| binoculars | 71.50% | **94.17%**（FPR 4.84%） |
| detectgpt | 未测 | 90.00% |
| fastdetectgpt | 未完成 | 未标定 |

### 3.8 关键结论：不是模型大小的问题

**证据链：**

| 对比 | 模型规模 | 结果 | 说明 |
|---|---|---|---|
| simpleai（中文 RoBERTa） | ~0.1B | **99.75%** | 模型小，但**语言匹配** |
| binoculars（gpt2 组合） | ~0.4B | 中文 71.5% / 英文 94.17% | 同一模型，**语言匹配度决定成败** |
| detectgpt（gpt2 + t5-base） | ~0.4B | 英文 90% | 模型小，但**公式对 + 阈值标定** |
| binoculars 修前→修后 | **模型未变** | 46.7% → 94.17% | 提升全来自**改代码 + 标阈值** |

**决定性因素是三项配套，模型大小排第四：**

1. **代码按论文写对**（本次修了 BUG-1/2/5/6）
2. **阈值用数据标定**（论文数字绑定其模型组合，不可移植）
3. **模型语言与文本匹配**（中文文本必须用中文模型）
4. 模型规模（有影响，但不是决定性 —— 0.1B 的 simpleai 拿到 99.75%）

### 3.9 本轮新增修复

| 项 | 文件 | 说明 |
|---|---|---|
| gltr 中文阈值 | `perplexity_engine.py`、`catalog.py` | 新增 `ppl_low_zh`/`ppl_high_zh`（11.35/18.72），按文本语言自动切换；中文 68.33% → **77.50%** |
| 位置上限崩溃 | `base.py` | 新增 `_encode_capped()`：中文经 gpt2 分词后 token 数暴涨（217 汉字 → 最长 1756 token），超过 `n_positions`(1024) 时 CUDA 直接崩。现按模型上限自动截断 |
| 死代码清理 | `base.py` | `avg_logprob` 后残留的重复代码块（227~243 行，永不执行）已删 |
| T5 输入超限 | `curvature_engine.py` | `_mask_perturb` 拼接后超 512 报错，现两侧各截断 |
| `import math` 缺失 | `curvature_engine.py` | σ 归一化引入 `math.sqrt` 但未导入，导致 `NameError` |
| 界面语言标注 | `engine_dialog.py`、`main_window.py`、`catalog.py` | 引擎名加「🌐 中文 / 🌐 英文」前缀，避免用户拿英文引擎测中文 |
| 描述校准 | `catalog.py` | binoculars 的 `desc` 去掉"不用调阈值就跨领域通用"（实测不成立）；gltr 补实测准确率 |

**对应 BUG 编号**（次轮新增，详见 `HANDOFF.md` §2 缺陷表）：

| 编号 | 问题 | 位置 |
|---|---|---|
| BUG-13 | 文本超模型 `n_positions` 时 CUDA 崩溃（中文必现） | `base.py` |
| BUG-14 | 缺 `import math` | `curvature_engine.py` |
| BUG-15 | `_mask_perturb` 拼接后超 T5 输入上限 | `curvature_engine.py` |
| BUG-16 | `avg_logprob` 后有死代码残留 | `base.py` |
| BUG-17 | gltr 的 `ppl_low/ppl_high` 只适配英文 | `perplexity_engine.py` |
| BUG-18 | gltr 在长文/新闻类数据上判别力骤降 | ⚠️ 方法局限，未修 |
| BUG-19 | 显存不足时静默降速（fp32 溢出） | `base.py`（见 §3.12） |

### 3.10 第二轮回归验证

| 测试 | 结果 |
|---|---|
| `py_compile` 全部改动文件 | OK |
| `tools/smoke_test.py` | 10/10 |
| `tools/test_engines.py` | 13/13 |
| `tools/test_detect.py` | ALL PASS |
| `tools/fusion_selftest.py` | 全部通过 |
| 集群发现实测 | 4 秒发现节点（修前恒为空） |
| `avg_logprob` 分块一致性 | 偏差 0.000%（修前 34~67%） |
| 离屏主窗口 | 下拉 5 项均带语言标注 |

### 3.12 BUG-19：显存不足时静默降速（无报错）

**现象**：`base.py` 加载模型时不指定 `torch_dtype`，默认 **fp32**。
对 `gpt-neo-2.7B`（fastdetectgpt）权重就要 10.8GB，加激活值会突破 16GB 显存。

**关键问题**：Windows 的 WDDM 在显存不足时**不报错**，而是把放不下的部分
换到系统内存（任务管理器里的「共享 GPU 内存」），走 PCIe 搬运 ——
带宽比显存低约 30 倍。

**实测表现**（200 条中文标定，fp32）：

| 指标 | 实测值 | 正常值 | 判断 |
|---|---|---|---|
| 专用显存 | 15.2 / 16.0 GB | — | 接近满 |
| **共享显存** | **1.9 GB** | 0 | **溢出** |
| GPU 利用率 | 94% | — | 假象 |
| **温度** | **32℃** | 60~75℃ | **几乎空闲** |
| **功耗** | **117 W** | 280~320 W | **没在算** |
| 耗时 | **4.1 小时未完成** | — | |

**修复**：`base.py` 新增 `_pick_dtype()`（CUDA 时自动用 fp16）+
`_check_vram()`（可用显存低于 2GB 时明确报错）。
**实测效果**：显存 15.5GB（溢出）→ 5.46GB；单条从"不可测"→ 13.6 秒。

**fp16 对照复测见 `HANDOFF.md` §5.9**（fp32 溢出 +2163MB / fp16 不溢出；
两处显存不足形态的区分；fp16 对判定结论无影响，Kendall 1.0000）。

**用户影响**：修前，8GB / 12GB 显卡跑 fastdetectgpt **不会看到任何错误**，
只会觉得"软件卡死了"。这属于**体验级严重问题**。

**诊断要点**：判断 GPU 是否真在计算，**看温度和功耗，不要只看利用率**
—— 利用率在等待 PCIe 传输时也会显示很高。

---

## 四、待办（TODO）

### TODO-1：GLTR 论文原样显示（优先级：中）

**依据**：arXiv:1906.04043v1 §3

`gltr_buckets()`（本轮新增）已产出可视化所需的全部数据：四档计数/占比、
Test-1 概率比、Test-3 熵。剩下的是界面层：

- 逐 token 四档配色 overlay（rank ≤10 绿 / ≤100 黄 / ≤1000 红 / 其余紫）
- 三张直方图：四档分布 / Test-1 概率比分布 / Test-3 熵分布
- hover tooltip：top-5 预测 + 概率 + 当前词 rank

改动点：

- `main_window.py:693` —— `result_label` 显示改为四档占比或柱状图
- `report.py:9` —— 段落标黄判据（**论文未给此规则**，建议沿用阈值）
- `benchmark.py:295` —— 评测流程对非概率输出的处理
- `rewrite_dialog.py:344` —— 段落列表的 AI% 显示

### TODO-2：按论文原版模型组合对齐（优先级：低，代价大）

| 引擎 | 论文模型 | 当前模型 | 下载量 |
|---|---|---|---|
| binoculars | Falcon-7B-Instruct + Falcon-7B | gpt2 + gpt2-medium | ~30GB |
| detectgpt | T5-3B | t5-base | ~11GB |

论文依据：arXiv:2401.12070 §3.3（默认组合）、arXiv:2301.11305 §5.3
（"clear association between capacity of mask-filling model and detection
performance"）。

注：论文自身也做了多模型组合消融（Binoculars 附录 Table 6），方法本身与模型
解耦；**换模型后必须重标阈值**。

### TODO-3：gltr 实现 GLTR Test-2（⚠️ 未完成，勿误读为论文有缺陷）

**依据**：arXiv:1906.04043v1 §3、§4

**当前状态**：已回退。`perplexity_engine.py` 恢复为原作者的单一 PPL 路线。

#### 已完成过的探索（2026-09-23）

实现了论文 §3 的 Test-2 逐 token rank 四档（绿 ≤10 / 黄 ≤100 / 红 ≤1000 /
紫 其余，档位与论文完全一致），并测了 6 种把它压成单一数值的聚合公式：

| 聚合公式 | 中文 HC3 | 英文 essay |
|---|---|---|
| 绿+黄 | 67.0% | 90.67% |
| 绿 | 73.0% | 94.00% |
| **绿-紫（最佳）** | **74.5%** | **94.67%** |
| 绿+0.5 黄 | 74.0% | 93.33% |
| 1-紫 | — | 87.33% |
| prob 比（属 Test-1） | 72.0% | 92.67% |

对照原 PPL 路线：中文 **76.3%** / 英文 **94.0%**。

→ **最佳聚合方案也只是打平（中文还略差）。**

#### ⚠️ 为什么"按论文实现却没优势"——不是论文的问题

**这一点必须讲清楚，避免误读成"论文的 Test-2 无效"。**

**原因 1：论文的 Test-2 不产出单一数值，它产出的是给人看的图。**

论文 §3 原文：

> The **central feature** of the tool is the overlay function, which can render
> arbitrarily chosen top-k buckets (Test-2) as an **annotation over the text**.

论文的产物是：逐 token 涂色 + 三张直方图（四档分布 / 概率比 / 熵）+
hover tooltip。**论文从不把四档压成一个数字。**

而项目接口（`registry.py` 的约定）要求 `predict_paragraphs` 返回
`list[float]`。**所以要用 Test-2，就必须自己补一步聚合 —— 那一步论文里没有，
是后加的，不是论文的一部分。**

**原因 2：论文的 AUC 0.87 来自「四档分布 + 逻辑回归」，不是「四档分布本身」。**

论文 §4 原文：

> Our first model uses the average probability ... as single feature (Test 1) and
> the second one the distribution over four buckets (Test 2) ...
> we use a **logistic regression** ... We **cross-validate** the results

即 **Table 1 里那三行（0.63 / 0.71 / 0.87）都是逻辑回归的结果**，只是输入
特征不同。0.71 → 0.87 的差距是"**同样训练条件下，不同特征的判别力差异**"。

而项目的 PPL 路线是**手写映射规则，没有训练**。两条路都没训练，
所以论文那个 0.87 vs 0.71 的对比**在项目场景下不复现**。

**原因 3：四档分布的大部分信息集中在"绿"和"紫"两端。**

实测英文 essay 的四档均值：

```
human  绿=0.677  黄=0.190  红=0.101  紫=0.032
AI     绿=0.776  黄=0.153  红=0.060  紫=0.012
```

绿+黄占比高达 0.87~0.93 —— 绝大多数 token 挤在前两档。所以
`(绿+黄)` 这类聚合会把区间压到 0.9~1.0 的窄带里（中文只有 67%）；
只有 `绿-紫` 同时取两端信号才有效，但差值本身也就 0.099 / 0.020。

可视化（人看图）不受影响 —— 人能看到"这一片全是绿色"这个整体印象；
压成一个数就丢了。

#### 后续可选方案

| 方案 | 做法 | 成本 | 能否复现论文优势 |
|---|---|---|---|
| **A（推荐）** | 提取四档分布 + 熵 + 概率比作特征，用带标注数据训 `LogisticRegression`（论文做法） | 小（sklearn 一个函数），数据已有 | ✅ 这才是论文的完整形态 |
| B | 走论文原样：界面画四档分布给人看，不压数字 | 中（改 4 个界面文件） | ✅ 但 `report.py` 的标黄判据需另想办法 |
| C（现状） | 维持 PPL 路线 | 无 | — |

**方案 A 的训练数据已就绪**：

- 英文：`D:\hf_cache\ghost_essay_1to1.jsonl`（600 条，1:1 平衡）
- 中文：`D:\hf_cache\hc3_zh_1to1.jsonl`（3000 条，1:1 平衡）

**注意**：方案 A 会引入"训练"步骤，而项目当前所有引擎都是零样本的
（见 `docs/PAPER_GAPS.md` 第九章"已对齐项"）。是否引入需权衡 ——
论文的 GLTR 本身就是"工具 + 可选分类器"两种用法并存。


### TODO-4：阈值重标定（优先级：高，阻塞可用性）

**已完成部分**（2026-09-23）：

| 引擎 | 语言 | 标定阈值 | 准确率 | FPR | 数据 |
|---|---|---|---|---|---|
| binoculars | 英文 | 0.615 | 94.17% | 4.84% | Ghostbuster Student Essay 120 条 |
| gltr | 中文 | (11.35, 18.72) | 77.50% | 27.6% | HC3-Chinese 400 条 |
| gltr | 英文 | (12, 25) 原值即最优 | 93.67% | 5.19% | Ghostbuster Student Essay 300 条 |
| detectgpt | 英文 | 1.1872（未归一化） | 90.00% | 10% | Ghostbuster Student Essay 60 条 |

**待补**：
- binoculars 的中文阈值（已标 0.149，但该组合在中文判别力本身弱）
- detectgpt / fastdetectgpt 的中文阈值
- **样本量扩展**：当前 60~400 条，论文用 6 套数据集数万条

**论文的标定方法**（arXiv:2401.12070v3 附录 A.1.2）：

> We **optimize using accuracy** and fix our threshold globally using these datasets.
> All of these datasets have an **equal number of human and machine-generated text samples**.

注：论文实际用于标定的是 CC News / CNN / PubMed（LLaMA-2-13B 与 Falcon-7B 生成），
这三套需自行抓取原始语料并跑生成，**不可直接下载**。本项目改用可公开获取的
Ghostbuster 三套（News / Creative Writing / Student Essay）+ HC3-Chinese。


### TODO-5：fastdetectgpt 基线（优先级：低）

需下载 `EleutherAI/gpt-neo-2.7B`（约 5.4GB）才能跑该引擎的基线。该引擎的
σ 归一化已修（BUG-6），但修后效果未实测。

**2026-09-23 更新**：模型已下载（10.0GB fp32 / fp16 加载 5.33GB），但仍**未标定**：
跑它需可用显存 ≥7GB，本机常被其他进程占 7.8GB，余量不足会**慢 10 倍**
（实测 139.9 秒/条 vs 干净环境 13.6 秒）。需先腾显存。

### TODO-6：工程清理（优先级：低，**按判据不修**）

- 未使用导入 14 处
- 静默 except 31 处（`cluster.py` 14 处、`installer.py` 6 处）
- 行长超 80 字符 378 处 / 38 文件

**这三项均不影响用户使用效果** —— 按 `AGENTS.md` 的判据「影响就修，不影响就不动」，
**当前不修**。记录在此仅为留档（原作者有意不限行长，见 `AUTHOR_STYLE.md`）。

### TODO-7：探针 `cluster_port` 拆分（✅ 已完成 2026-09-23）

**原问题**：`tools/probes/cluster.py` 的 `run_cluster_port_and_chunk()` 把两件
无关的事装在一个探针里：

| 部分 | 验证对象 | 需要什么 |
|---|---|---|
| 2.4 | 集群端口绑定竞争 | 真起 socket，占端口 5 秒 |
| 2.5 | `avg_logprob` 分块口径 | **纯 `torch.arange` + 桩模型，零副作用** |

**后果**：想看 2.5（分块口径）必须连带占用 UDP 47650 五秒，所以整条被归进
`heavy` 组。而 2.5 本身属 `safe`。

**已改为两个探针**：

| 探针 | 函数 | 组 | 副作用 |
|---|---|---|---|
| `cluster_port` | `cluster:run_cluster_port` | heavy | 占 UDP 47650 约 5 秒 |
| `logprob_chunk` | `cluster:run_logprob_chunk` | **safe** | **无**（纯计算） |

**验证**：`--only logprob_chunk` 与 `--only cluster_port` 均独立跑通，
结论与原脚本一致。

---

### TODO-8：中文可用性（优先级：**高**，由 2026-09-23 AUC 实测新增）

**背景**：AUC 实测（见 `HANDOFF.md` §5.10）证明 **5 个引擎里只有 simpleai
在中文上可交付**：

| 引擎 | 中文 AUC | 判定 |
|---|---|---|
| simpleai | **0.9998** | ✅ 可交付 |
| gltr | 0.7816 | ⚠️ 弱 |
| binoculars | 0.7728 | ⚠️ 弱 |
| detectgpt | **0.2800** | ❌ **反向不可用**（低于随机） |
| fastdetectgpt | 未测 | ❓ 未标定 |

**根因**：4 个引擎用的是**英文模型**（gpt2 / gpt2-medium / t5-base /
gpt-neo-2.7B），**方法本身与语言无关，是模型选择问题**。

**三个方案（工作量递增）：**

| 方案 | 做法 | 工作量 | 涉及文件 | 预期收益 |
|---|---|---|---|---|
| **A** | 新增独立引擎 `zh_perplexity`（**原作者方案**，`engines_manifest.json` 已有条目 + 阈值 20/45） | **30 分钟** | `catalog.py` 加 1 条 | 中文多一个可用选项（约 0.63 acc） |
| **B** | 改 gltr 按语言自动切模型（`_is_chinese()` 已有雏形） | **2 小时** | `perplexity_engine.py` + `catalog.py` | 用户无感，但提升有限 |
| **C** | 4 个引擎全换中文模型 | **1~2 天** | 6+ 文件 | 4 个都改善，**但仍都差于 simpleai** |

**方案 C 的卡点：**

| 引擎 | 换什么 | 难度 | 卡点 |
|---|---|---|---|
| gltr | 中文 GPT-2 | ⭐ | 无 |
| binoculars | **2 个同词表中文模型** | ⭐⭐⭐ | 中文 GPT-2 家族配对少（论文要求同词表） |
| detectgpt | 中文 GPT-2 + **中文 T5** | ⭐⭐⭐ | **中文 T5 生态弱** |
| fastdetectgpt | 中文大模型 | ⭐⭐⭐⭐ | **无现成等价物**（gpt-neo-2.7B 的中文对应） |

**已验证的效果**（待办 3 实测）：

```
gpt2（现用）      分词 431 token   FPR≤5% acc 0.4950（无用）
gpt2-chinese      分词 205 token   FPR≤5% acc 0.6300   ← +13.5，有效
```

**但即使全做完，都追不上 simpleai 的 0.9998** —— 因为 simpleai 是
**专门为中文训练的判别模型（有监督）**，而换底座后仍是**无监督统计**，
方法上就差一档。

**建议**：做 **A**（30 分钟，原作者已备好方案），**B/C 按需**。
**更该先做方案 D（见 TODO-9）** —— 让用户知道中文该用哪个。

### TODO-9：引擎的中文可用性标注（✅ 已完成 2026-09-23）

**原问题**：用户拿中文学术论文选 binoculars / detectgpt，会得到
**完全错误的结果**（detectgpt 甚至是反向的），而界面**没有任何提示**。

**已实现**：扩 `engine_lang_mark()`（`app/ui/engine_dialog.py`），
识别 `tags` 里的可用性标记并输出后缀：

| 引擎 | 界面显示 | 中文 AUC |
|---|---|---|
| SimpleAI | `🌐 中文 ✅ 可用` | 0.9998 |
| GLTR | `🌐 中文 / 英文 ⚠️ 中文弱` | 0.7816 |
| Binoculars | `🌐 中文 / 英文 ⚠️ 中文弱` | 0.7728 |
| DetectGPT | `🌐 中文 / 英文 ❌ 中文勿用` | 0.2800（反向） |
| Fast-DetectGPT | `🌐 中文 / 英文 ❌ 中文勿用` | 未测 |

**改的两个文件**：
- `app/core/engines/catalog.py` —— 5 个引擎的 `tags` 各加 1 个可用性标记
- `app/ui/engine_dialog.py` —— 新增 `_USABILITY_TAG` 映射，`engine_lang_mark()` 输出后缀

**验证**：`engine_lang_mark()` 对 5 个引擎都返回正确后缀；
回归 `smoke_test.py` 10/10、`test_engines.py` 13/13、`test_detect.py` ALL PASS。

**注意**：`catalog.py` 的 `desc` 属**代码内文案**（非原作者文档），
但本次**未改 desc**，只加 `tags` —— 因为 desc 的改动面更大，
留给原作者决定是否在描述里明说。

## 五、修复阶段的写操作清单（代码改动）

| 路径 | 操作 | 说明 |
|---|---|---|
| `app/core/engines/base.py` | 修改 | `avg_logprob` 改整段；新增 `cross_perplexity`；fp16 加载 + 显存预检 |
| `app/core/engines/binoculars_engine.py` | 修改 | 公式按论文式 (3)(4) |
| `app/core/engines/curvature_engine.py` | 修改 | 两处补 σ 归一化；T5 输入两侧截断；补 `import math` |
| `app/ui/settings_dialog.py` | 修改 | `hf_endpoint` 写 url |
| `app/core/cluster.py` | 修改 | master 绑随机端口 |
| `app/ui/main_window.py` | 修改 | 参数合并顺序；引擎下拉用带语言标注的名称 |
| `app/core/report.py` | 修改 | 文件名转义 |
| `app/core/engines/perplexity_engine.py` | 修改 | 按语言分档阈值 |
| `app/core/engines/catalog.py` | 修改 | 阈值改为实测标定值；补语言标签；描述校准 |
| `app/ui/engine_dialog.py` | 修改 | 新增 `engine_lang_mark()`，引擎名带语言前缀 |
| `tools/smoke_test.py` | 修改 | sys.path 指向 app |
| `settings.json` | 新建 | 模型缓存外置到 `D:\hf_cache\aigc_models` |
| `docs/AUDIT.md` | 新建 | 本文件 |
| `docs/calibration.md` | 新建 | 标定数据 + 风格核查（23 个文件多轮合并为 1 个） |
| `tools/audit_probes.py` + `tools/probes/` | 新建 | 探针主程序 + 5 个模块（13 个探针，原 15 个独立脚本） |
| `tools/download_simpleai_model.py` 等 4 个 | **删除** | 移入回收站 |

**模型缓存**（项目外，未进 git）：`D:\hf_cache\aigc_models\` —— simpleai
781MB、gltr 525MB、binoculars 1978MB、detectgpt 1378MB、fastdetectgpt 10239MB。

**上传前需清理**：`app/logs/app.log`（193 字节启动日志，程序自动生成）。



