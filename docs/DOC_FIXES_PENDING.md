# 用户文档待修订清单（原作者的文档，暂不改）

- 记录日期：2026-09-23
- 背景：用户要求**不动原作者的文档**（`README.md`、`README.en.md`、
  `使用手册.md`、`CHANGELOG.md`），把待修订内容记在本文件里，等与原作者
  沟通后再统一处理。
- 配套文档：`docs/AUDIT.md`（代码修复记录）、
  `docs/PAPER_GAPS.md`（与论文的差异）

---

## ⚠️ 改动准则（用户明确要求）

1. **不改原作者的任何文档**
2. 待修订内容记录在本文件
3. 若将来修订，**依据必须是实测数据**（见 `docs/calibration.md`）

---

## 零、`engines_manifest.json` 的问题（可选引擎清单）

> 注：该文件是**可选引擎清单**（用户填 URL 拉取）。以下只记**实测证明有误**的项。
> —— 2026-09-23 说明：原「URL 指向原作者仓库」一条已撤除，
> 因为那是**功能设计**（清单就该指向发布地址），不属缺陷。

### 0.1 【阈值有误】`zh_perplexity` 的阈值会让人写文本 95% 被判 AI

**位置**：`engines_manifest.json:75`

```json
"params": { "ppl_high": 45.0, "ppl_low": 20.0 }
```

**实测（2026-09-23，HC3-Chinese 200 条 1:1）：**

| 阈值组 | 准确率 | FPR | 说明 |
|---|---|---|---|
| 原值 (20, 45) | **0.5200** | **0.9500** | ❌ **95% 的人写文本被判 AI** |
| 实测最优 (5.40, 14.40) | 0.8650 | 0.1800 | 误报偏高 |
| **已改为 FPR≤5% 版 (2.88, 7.68)** | **0.6300** | **0.0400** | ✅ 可交付 |

**原因**：中文 GPT-2 的 PPL 远低于英文。实测**中文 human 中位仅 13.64**
（英文为 29.50），而 `ppl_low=20` 高于它 → 人写样本全部落到 `<=lo` 一侧，
被判 AI。

**同时修正了 `desc`**：原文写"阈值已按中文调整（PPL 20~45）"，
把这个错误区间对外宣称了，已改为"注意：中文 PPL 远低于英文，阈值与英文组不通用"。

**复现**：`python tools/audit_probes.py --only zh_threshold`
**数据**：`docs/calibration.md` §2.8

**状态**：✅ **已修（2026-09-23）** —— 改动的是该 JSON 里的 `params` 与 `desc`，
它们属**引擎配置**（与 `catalog.py` 内的阈值同类），修正依据为实测。

---

## 一、README.md

### 1.1 【错误信息】Binoculars 写着"免调阈值"

**位置**：`README.md:94`

> | **Binoculars** | 同词表双模型交叉困惑度比 `B = logPPL_observer / crossPPL_performer`，B 越小越像 AI；**只看比值，免调阈值**；ICML 2024 |

**问题 1：「免调阈值」与实测不符。**

实测（Ghostbuster Student Essay，120 条 1:1）：

| 阈值 | 准确率 | FPR |
|---|---|---|
| 论文原值 0.9015 | 60.3% | 25.5% |
| **实测标定值 0.615** | **94.17%** | **4.84%** |

**阈值配错会让准确率掉 34 个百分点。** "免调阈值"这个说法会误导用户
以为不需要关心阈值。

注：论文原文说的是 "we **optimize using accuracy** and fix our threshold
globally using these datasets"（附录 A.1.2）—— 论文自己就是**调**阈值的，
只是调完固定下来。所以"免调"这个描述与论文也不符。

**问题 2：公式未标明 log 域。**

原文写 `B = logPPL_observer / crossPPL_performer`，而论文式 (4) 是
`B = logPPL / log-xPPL` —— **分子分母都在 log 域**。写 `crossPPL`（而非
`log-xPPL`）容易被理解成实数域困惑度，而这正是项目原代码出 bug 的地方
（用 `exp()` 跑到实数域，导致 B 值量级错 100 倍、恒判 AI）。

**建议改为**：

> 同词表双模型交叉困惑度比（对数比值）`B = logPPL_observer / log-xPPL`，
> B 越小越像 AI；换模型后需按论文方法重标阈值

### 1.2 【与论文不符】DetectGPT / Fast-DetectGPT 的公式漏了 σ 归一化

**位置**：`README.md:92-93`

> | **Fast-DetectGPT** | **按论文的条件概率曲率实现**：用打分模型自身采样构造扰动样本 x̃，比较 `logP(x) − E[logP(x̃)]` |
> | **DetectGPT** | **按论文的掩码扰动实现**：T5 补全随机挖掉的片段得到 x̃，比较对数概率曲率 |

**问题**：两处都写着"按论文实现"，但列出的公式**都漏了方差归一化**。

论文原文：

| 论文 | 公式 |
|---|---|
| DetectGPT（arXiv:2301.11305 §4 Alg.1） | `d = (logp(x) − μ̃) / √σ̃` |
| Fast-DetectGPT（arXiv:2310.05130 §2.3 式 3） | `d = (logp(x\|x) − μ̃) / σ̃` |

**而代码里是有 σ 的**（我在 `curvature_engine.py` 的两处都补上了）。
所以是**文档没跟上代码**。

**建议改为**：

> 比较对数概率曲率 `(logP(x) − μ̃) / σ̃`（μ̃、σ̃ 为扰动样本分数的均值与标准差）

### 1.3 【易混淆】"中英双语"指的是界面语言，不是查重语言

**位置**：`README.md:30`、`:45`

> | **中英双语** | 软件界面与安装器均支持一键切换 中文 / English |

**问题**：项目定位已改为**「中英双语论文查重」**（用户 2026-09-23 决定）。
而 README 里的"中英双语"指的是 **UI 界面语言**。两者同名，容易混淆。

**且这是用户最需要知道的事**：5 个检测引擎里，**只有 simpleai 是中文模型**，
其余 4 个源自英文模型。实测：

| 引擎 | 中文 | 英文 |
|---|---|---|
| simpleai | ✅ 99.75% | ❌ FPR 100% |
| gltr | ⚠️ 74.67% | ✅ 93.67% |
| binoculars | ❌ FNR 100% | ✅ 94.17% |
| detectgpt | ❓ 未测 | ✅ 90% |
| fastdetectgpt | ❓ 未测 | ❓ 未测 |

**用户拿中文学术论文选 binoculars，会得到"AI 率 0%"这种完全错误的结果。**

**建议**：
- 在「功能介绍」表的"中英双语"一行，区分"界面语言"与"检测语言"
- 在「检查引擎（5 个）」表里为每个引擎补**语言标注 + 实测准确率**

### 1.4 【需更新】"全部已实现，不是纸面引用"

**位置**：`README.md:82`

> ## 集成的 9 项方法（全部已实现，不是纸面引用）

**问题**：修前这句话**不成立** —— Binoculars 的公式是错的（恒判 AI）、
DetectGPT / Fast-DetectGPT 缺 σ、GLTR 没实现 Test-2。

**修复后**：公式层面的"已实现"成立，但仍有差异（见 `docs/PAPER_GAPS.md`）：

| 项 | 状态 |
|---|---|
| Binoculars 公式 | ✅ 已按论文（含交叉项） |
| DetectGPT / Fast-DetectGPT σ | ✅ 已补 |
| GLTR 的 Test-2（rank 四档） | ❌ 未实现（现为 PPL 路线，论文 Test-1 的退化版） |
| Fast-DetectGPT 的条件独立采样 | ❌ 未实现（现为自回归生成） |

**建议**：保留这句话，但在下方补一句"具体实现差异见 docs/PAPER_GAPS.md"，
或直接把 GLTR 一行的描述改准确（不写"按论文实现"，改写实际做法）。

---

## 二、使用手册.md

### 2.1 【错误信息】Binoculars 写着"免调阈值"

**位置**：`使用手册.md:35`

> - **Binoculars**（约 1.9GB，零样本，双模型交叉困惑度，**免调阈值**）

**问题**：与 `README.md:94` 同一处错误，详见 1.1。

### 2.2 【需补充】引擎列表缺语言标注

**位置**：`使用手册.md:31-35`

> - **SimpleAI 中文检测**（约 400MB，推荐，中文论文首选）
> - GLTR 困惑度检测（约 500MB，英文文本较好）
> - **Fast-DetectGPT**（约 5.4GB，零样本，条件概率曲率，建议显卡）
> - **DetectGPT**（约 1.4GB，零样本，掩码扰动，CPU 勉强可跑）
> - **Binoculars**（约 1.9GB，零样本，双模型交叉困惑度，免调阈值）

**问题**：这是用户**选引擎的那一步**（第二节「AI 检测」），而列表里：

| 引擎 | 现有提示 | 缺什么 |
|---|---|---|
| SimpleAI | "中文论文首选" | ✅ 有 |
| GLTR | "英文文本较好" | ⚠️ 未说中文能用（实测 74.67%） |
| Fast-DetectGPT | 无语言提示 | ❌ **缺** |
| DetectGPT | 无语言提示 | ❌ **缺** |
| Binoculars | 无语言提示 | ❌ **缺** |

**用户不知道**：Fast-DetectGPT / DetectGPT / Binoculars **都是英文模型**，
拿它们测中文会得到完全错误的结果。

**建议改为**（附实测数据）：

> - **SimpleAI 中文检测**（约 400MB，🌐 中文专用，中文论文首选，实测 99.75%）
> - GLTR 困惑度检测（约 500MB，🌐 中英双语，英文 93.7% / 中文 74.7%）
> - **Fast-DetectGPT**（约 5.4GB，🌐 英文，零样本，建议显卡，中文未测）
> - **DetectGPT**（约 1.4GB，🌐 英文，零样本，CPU 勉强可跑，中文未测）
> - **Binoculars**（约 1.9GB，🌐 英文，零样本，双模型交叉困惑度，英文 94.2%）

### 2.3 【需更新】"不确定就用默认的 SimpleAI"

**位置**：`使用手册.md:38`

> 不确定就用默认的 SimpleAI。

**问题**：这句话在**中文场景下是对的**，但项目定位已改为**双语**。
英文论文用户照做会拿到 **FPR 100%** 的结果。

**建议改为**：

> 不确定就用默认的 SimpleAI（中文）。
> **英文论文请改用 GLTR / DetectGPT / Binoculars** —— SimpleAI 是中文专用模型，
> 对英文会全部判成 AI。

---

## 三、README.en.md

**行号已核查**（2026-09-23）：

| # | 行号 | 原文（节录） | 问题 |
|---|---|---|---|
| 1 | **:108** | Binoculars: `B = logPPL_observer / crossPPL_performer`; **ratio-based, no threshold tuning** | ❌ **"no threshold tuning" 与实测不符**（同 1.1）；且 `crossPPL` 未标 log 域 |
| 2 | **:106** | Fast-DetectGPT: `we compare logP(x) − E[logP(x̃)]` | ❌ **漏 σ**（论文式 3 是 `(logp − μ̃)/σ̃`） |
| 3 | **:107** | DetectGPT: `we compare log-probability curvature` | ⚠️ 未写公式，但描述含糊；论文 Alg.1 是 `(logp − μ̃)/√σ̃` |
| 4 | **:30 / :46** | `**Bilingual**` / `**Bilingual UI**`：指 **UI 界面语言** | ⚠️ 与新定位「双语查重」易混淆；未说明 5 个引擎的语言能力 |
| 5 | **:23 / :38** | `5 detection engines` 列表 | ⚠️ **缺语言标注** —— 4 个是英文模型 |
| 6 | **:11** | `the app UI itself is bilingual` | ✅ 措辞准确（明确说的是 UI） |
| 7 | **:29 / :41** | `Highly customizable — Threshold, ...` | ✅ 无问题 |

**建议改法**（与中文版保持一致）：

**:108** →
> Cross-log-perplexity ratio of two same-tokenizer models,
> `B = logPPL_observer / log-xPPL`; lower B means more AI-like;
> **re-tune the threshold when you swap models**; ICML 2024

**:106** →
> ... then we compare the log-probability curvature
> `(logP(x) − μ̃) / σ̃` (μ̃, σ̃ = mean and std of perturbation scores); ICLR 2024

**:23 / :38** →
> | **5 detection engines** | SimpleAI Chinese (default, 🇨🇳 99.8%),
> GLTR (🇨🇳 74.7% / 🇬🇧 93.7%), Fast-DetectGPT (🇬🇧), DetectGPT (🇬🇧 90%),
> Binoculars (🇬🇧 94.2%) — or any HuggingFace model |
>
> **Note**: only SimpleAI is a Chinese model. The other four are English-based
> and will produce **wrong results on Chinese text**.


---

## 四、CHANGELOG.md

**状态**：未发现问题。

理由：CHANGELOG 记录的是"每个版本改了什么"。本次修复**尚未发布新版本**，
所以不需要改动。等发布时再补一条记录即可。

**建议**：发布新版本时在 CHANGELOG 里加一条，例如：

```
## v1.2.9
- 修复 Binoculars 的交叉困惑度计算（原实现分母量纲错误，导致所有文本被判为 AI）
- 修复 avg_logprob 的分块计算（分块与整段结果不一致）
- 修复集群主节点无法发现工作节点（端口冲突）
- 修复设置里保存 HuggingFace 镜像地址时丢协议头
- 修复显存不足时的静默降速（自动改用半精度加载 + 不足时明确报错）
- 修复中文文本超过模型位置上限时的崩溃
- 新增：引擎名带语言标注（🌐 中文 / 🌐 英文）
- 新增：GLTR 支持中文阈值（中文准确率 68% → 75%）
```

---

## 五、修订时的依据（实测数据位置）

**所有修订都要有实测支撑**，数据在 `docs/calibration.md`：

| 文件 | 内容 |
|---|---|
| `calibration.md` | **标定数据**：中/英阈值依据、σ 实测、风格核查 |
| `../AUDIT.md` §3.1 | 4 个引擎的修前基线 + 修前逐条概率 |

---

## 六、汇总：待修订条目

| # | 文件 | 位置 | 类型 | 严重度 |
|---|---|---|---|---|
| 1 | README.md | :94 | **错误信息**（免调阈值） | 高 |
| 2 | README.md | :94 | 公式未标 log 域 | 中 |
| 3 | README.md | :92-93 | 与论文不符（漏 σ） | 中 |
| 4 | README.md | :30, :45 | 易混淆（双语含义） | 高 |
| 5 | README.md | :82 | 描述需补差异说明 | 低 |
| 6 | 使用手册.md | :35 | **错误信息**（免调阈值） | 高 |
| 7 | 使用手册.md | :31-35 | 缺语言标注 | 高 |
| 8 | 使用手册.md | :38 | 引导语在英文场景下会误导 | 高 |
| 9 | README.en.md | :108 | **"no threshold tuning" 与实测不符** | 高 |
| 10 | README.en.md | :106-107 | 漏 σ（与论文不符） | 中 |
| 11 | README.en.md | :30, :46 | "Bilingual" 含义易混淆 | 高 |
| 12 | README.en.md | :23, :38 | 引擎列表缺语言标注 | 高 |
| 13 | CHANGELOG.md | — | 发布时补记录 | 低 |

**其中 1、4、6、7、8、9、11、12 属"影响用户使用效果"** —— 用户会因此
选错引擎、拿到完全错误的结果，且无从察觉。

**总计 13 条，涉及 4 个文件。全部暂不改动，等与原作者沟通后统一处理。**


