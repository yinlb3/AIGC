# HANDOFF — 交接说明

- 日期：2026-09-23
- 项目：`d:\Project\AIGC`（AI 检测工具箱 v1.2.8，原作者 gxgx3456）
- 本次工作：代码审查、修复与实测验证

---

## 1. 当前状态

### 环境

```
解释器：C:\ProgramData\miniconda3\envs\pytorch\python.exe
        Python 3.12.8 / torch 2.8.0+cu129 / CUDA 12.9 / RTX 4080 SUPER 16GB
        transformers 5.17.0（与代码兼容，已实测，不要降级）/ PySide6 6.9.2
```

### 项目外数据（有意保留，勿删）

| 路径 | 内容 |
|---|---|
| `D:\hf_cache\aigc_models\` | 5 个模型：simpleai 781MB / gltr 525MB / binoculars 1978MB / detectgpt 1378MB / fastdetectgpt 10239MB |
| `D:\hf_cache\ghostbuster-data\` | Ghostbuster 数据集（英文，1.5GB） |
| `D:\hf_cache\hc3_zh_1to1.jsonl` | HC3 中文 1:1 平衡集（3000 条） |
| `D:\hf_cache\ghost_essay_1to1.jsonl` | Ghostbuster 英文 1:1（600 条） |
| `D:\hf_cache\ghost_multi.jsonl` | Ghostbuster 三套合并（1194 条） |
| `D:\hf_cache\zh_gpt2\` | 中文 GPT-2（500MB，待用于换底座） |

模型缓存路径由 `settings.json` 的 `download.models_dir` 指定。该文件在 `.gitignore` 内，不会进仓库。

### Git

```
提交：bb87b41  fix: repair defects found by testing every engine
      60 files changed, 10034 insertions(+), 351 deletions(-)
作者：yinlb <yinlb3@foxmail.com>
远程：github.com/yinlb3/AIGC（非原作者仓库）
状态：已 push
```

### 定位变更（待与原作者同步）

项目从「中文论文查重」调整为 **「中英双语论文查重」**。英文能力自此是正式功能。

---

## 2. 已完成

### 测试结论

对全部引擎与周边各层用 13 个探针实测（无需下载模型即可复现）：

- **通过**：引擎清单 9 条、管理器多层合并、注册表与插件、修复类引擎、评测流水线、诊断与降重（含受保护片段往返）、界面构造、多卡分片、集群任务分发、代码库自身风格；4 个自带脚本原样通过；transformers 5.17 无需锁版本。
- **缺陷**：8 项确认（详见下），另有 5 项怀疑经测试不成立，已撤回。

### 修复的缺陷

| 问题 | 位置 | 结果 |
|---|---|---|
| Binoculars 恒判 AI（分母跑出 log 域 + 无交叉项 + 量纲混用） | `binoculars_engine.py` | 准确率 46.7% → **94.17%** |
| `avg_logprob` 分块口径错 | `base.py` | 偏差 34~67% → **0.000%** |
| DetectGPT / Fast-DetectGPT 缺 σ 归一化 | `curvature_engine.py` | 补上（实测说明见 §5.4） |
| 集群发现端口绑定竞争 | `cluster.py` | 修前恒为空 → **4 秒发现节点** |
| `hf_endpoint` 写成裸域名 | `settings_dialog.py` | 下载恢复 |
| 引擎清单参数覆盖用户参数 | `main_window.py` | 顺序修正 |
| 中文长文本超 `n_positions` 崩溃 | `base.py` | 新增 `_encode_capped()` |
| 显存不足静默降速（fp32 溢出） | `base.py` | 新增 fp16 加载 + 显存预检 |
| T5 输入超 512 token | `curvature_engine.py` | 两侧截断 |
| 缺 `import math` | `curvature_engine.py` | 补上 |
| 报告文件名未转义 / `smoke_test.py` 路径错 | `report.py` / `tools/` | 修 |
| 引擎无语言标注（除 simpleai 外皆为英文模型） | `engine_dialog.py` / `main_window.py` / `catalog.py` | 加 🌐 标注 |
| 阈值不可移植 | `catalog.py` | 重标（见 §4.3） |

### 产出的文档与工具

| 产出 | 内容 |
|---|---|
| `docs/AUDIT_2026-09-22.md` | 12 条缺陷的定位、修法与实测数据；5 篇论文核对；TODO |
| `docs/PAPER_GAPS.md` | 与所引论文的全部差异（11 项，分 S/A/B/C 级） |
| `docs/AUTHOR_STYLE.md` | 原作者风格 13 项实测对照（改动前必读） |
| `docs/DOC_FIXES_PENDING.md` | 原作者文档的待修订清单（13 条，暂不改） |
| `docs/calibration/` | 21 个实测数据文件 |
| `docs/baseline/` | 4 个引擎的修复后基线报告 |
| `tools/audit_probes/` | 13 个可复现探针 + README |
| `AGENTS.md` | 项目约定（供贡献者与 AI 助手阅读） |
| 删除 | 4 个废脚本（路径失效或功能重复） |

---

## 3. 待办

### 高优先级

| # | 事项 | 成本 | 说明 |
|---|---|---|---|
| 1 | 补测 detectgpt / fastdetectgpt 的中文表现 | 各约 45 分钟 | 双语定位的必需项 —— 这 2 个引擎的中文目前"未知" |
| 2 | gltr / binoculars 在同一批数据上的双语交叉验证 | 各约 30 分钟 | 现有数据来自不同数据集，不可直接比较 |
| 3 | 考虑换中文模型底座（`uer/gpt2-chinese-cluecorpussmall`） | 500MB（**已下载**） | 让中文侧不止 simpleai 一个可用选项。原作者在 `engines_manifest.json` 里已写过 `zh_perplexity` 条目，说明本有此意 |
| 4 | README / 使用手册同步"双语"定位 | 小 | 属原作者文档，需先与其沟通（见 §4.5） |

### 中优先级

| # | 事项 | 成本 |
|---|---|---|
| 5 | 采样数 k 从 5/10 提到论文值（100 / 10000） | 慢 10~20 倍 |
| 6 | Fast-DetectGPT 的条件独立采样（论文明确要求，未实现） | 改约 40 行 |
| 7 | 标定样本量扩到 5000+ | 需更多数据 |

### 低优先级

| # | 事项 |
|---|---|
| 8 | GLTR rank 四档可视化（论文原样） |
| 9 | 工程清理（行长 378 处、未用导入 14 处、静默 except 31 处） |

---

## 4. 关键决策

### 4.1 判据：是否影响用户使用效果

**影响就修，不影响就不动。** 据此：

- **修**：Binoculars 恒判 AI、显存静默降速、中文超长崩溃、引擎语言标注
- **不修**：行长超标、缺编码声明、静默 except（不影响行为）

### 4.2 代码风格跟随原作者，不套外部规范

原作者风格与通行规范 **9 项相反**：中文注释、`os.path.join`、双引号、不限行长、无文件头、目录不用 `src/`+`config/` 等。**这些是有意为之，不要"修正"。** 详见 `docs/AUTHOR_STYLE.md`。

### 4.3 阈值必须重标，不能照抄论文

论文阈值绑定各自模型组合：

| 引擎 | 论文阈值 | 论文模型 | 本项目模型 | 重标后 |
|---|---|---|---|---|
| Binoculars | 0.901 | Falcon-7B-Instruct + Falcon-7B | gpt2 + gpt2-medium | **0.615**（94.17% acc / 4.84% FPR） |
| GLTR | 12 / 25 | gpt2（英文） | 同 | 英文保持，**中文另加 11.35 / 18.72** |

论文附录 A.1.2 明确要求换模型后重新优化。GLTR 中文阈值的依据：中文人写文本 PPL 中位 17.18，英文 29.50，同一组阈值迁移不过去。

### 4.4 gltr 的 Test-2 实现后回退

实现了论文 §3 的 rank 四档（档位与论文一致），但压成单一数值后最佳方案只打平原路线，中文还略差。

**原因不在论文**：

1. 论文的 Test-2 产物是"涂色 + 直方图"，给人看图，不产出数值；项目接口要求返回 `list[float]`，所以"压成一个数"是后加的一步。
2. 论文 AUC 0.87 来自「四档分布 **+ 逻辑回归**」，Table 1 三行都是逻辑回归的结果；项目 PPL 路线无训练，该对比不复现。

**要复现需按论文做：四档 + 逻辑回归**（数据已就绪，见 `docs/AUDIT_2026-09-22.md` TODO-3 方案 A）。

### 4.5 原作者文档一律不改

`README.md` / `README.en.md` / `使用手册.md` / `CHANGELOG.md` 未作任何改动，待修订内容记在 `docs/DOC_FIXES_PENDING.md`。

### 4.6 定位改为双语（用户决定）

与原作者沟通后再动其文档。

---

## 5. 注意事项

### 5.1 环境坑

| 坑 | 说明 |
|---|---|
| **残留 `HF_HUB_OFFLINE=1`** | 会让下载报 "outgoing traffic disabled"，跑前先清 |
| 下载走镜像 | `$env:HF_ENDPOINT='https://hf-mirror.com'` |
| 符号链接警告 | `$env:HF_HUB_DISABLE_SYMLINKS_WARNING='1'` |
| 命令超时 | 超过 300 秒会被转到后台，需轮询文件看结果 |
| 控制台乱码 | PowerShell 编码问题，不影响程序，读输出文件即可 |

### 5.2 长任务必须带进度

```python
def prog(done, total):
    print("[%d/%d] %.0f%%" % (done, total, done * 100.0 / total), flush=True)
    #                                        flush 必须加，否则输出被缓冲

eng.predict_paragraphs(texts, dev, progress_cb=prog, **params)
```

跑全量前先用 3~5 条测单条耗时；预估超 30 分钟先报告再决定。

### 5.3 显存不足不报错，只变慢

Windows WDDM 在显存不够时不报错，而是把数据换到系统内存（「共享 GPU 内存」），走 PCIe —— 比显存慢约 30 倍。

**症状**：GPU 利用率 94%（假象）、**温度 32℃**、**功耗 117W**（正常 280W+）、跑得极慢。

**诊断**：看温度和功耗，不要只看利用率。`nvidia-smi` 看不到共享显存，要看任务管理器。

### 5.4 σ 归一化在小采样下反而有害

实测 DetectGPT：未归一化 90%，加了 `/√σ̃` 变 75%。

**原因**：σ 是估计量，项目只用 5~10 个样本估（论文用 100/10000），除以不稳的 σ 会放大噪声。

### 5.5 引用指标必须说明数据集

同一引擎、同一套 Ghostbuster 数据，gltr 表现：

- `essay` 子集：**93.67%**
- `essay + reuter + wp`（含新闻类）：**52~54%**

### 5.6 `settings.json` 含本机路径

`download.models_dir` 指向 `D:\hf_cache\aigc_models`。**发布前需删掉该文件或改回默认**，否则用户会遇到不存在的目录。

---

## 6. 文档索引

| 想了解 | 看哪个 |
|---|---|
| 有哪些缺陷、怎么修的 | `docs/AUDIT_2026-09-22.md` |
| 与论文差在哪 | `docs/PAPER_GAPS.md` |
| 代码风格基准 | `docs/AUTHOR_STYLE.md` |
| 原作者文档待修订项 | `docs/DOC_FIXES_PENDING.md` |
| 各引擎实测数据 | `docs/calibration/` |
| 修复前后对比 | `docs/baseline/` |
| 怎么复现验证 | `tools/audit_probes/README.md` |
| 项目约定 | `AGENTS.md` |

