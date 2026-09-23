# 原作者代码风格（改动时的对齐基准）

- 记录日期：2026-09-23
- 用途：本项目**遵循原作者风格**，不套用其他规范。改动代码前先看本表。
- 数据来源：扫描 git 已跟踪的 41 个 `.py`（排除 `tools/probes/`）
- 原始数据：`docs/calibration.md` 第三章（可重跑 `python tools/audit_probes.py --only style_report` 复现）

---

## ⚠️ 核心原则

**原作者已有的写法就是基准。新增/改动的代码要模仿它。**

不要按外部规范（如"注释全英文""强制 pathlib""单引号"）去改原作者代码 ——
那些规范与本项目风格**大部分相反**，改了反而不一致。

---

## 一、语言策略：**全中文**

| 项 | 常见规范 | **原作者实际** | 采用 |
|---|---|---|---|
| 行注释 | 英文 | **中文 · 227 处 / 29 个文件** | ✅ 中文 |
| docstring | 英文 | **中文 · 134 处 / 33 个文件** | ✅ 中文 |
| `raise` 异常消息 | 英文 | **中文 · 10 处 / 4 个文件** | ✅ 中文 |
| GUI 文本 | 中文 | 中文 | ✅ 中文 |

**最集中的几个文件**：

| 文件 | 中文注释 | 中文 docstring |
|---|---|---|
| `app/core/aigc_rules.py` | 28 | — |
| `installer/installer.py` | 28 | 19 |
| `app/core/diagnosis.py` | 24 | — |
| `app/core/engines/catalog.py` | 17 | — |
| `app/core/engines/base.py` | 13 | 14 |

**唯一例外**：`tools/` 里的测试脚本 `print` 输出用中文（面向使用者）。

---

## 二、路径与工具：**os.path 为主**

| 项 | 常见规范 | **原作者实际** | 采用 |
|---|---|---|---|
| 路径构造 | `pathlib.Path` | **`os.path.join()` · 75 处 / 18 文件**；pathlib **0 处** | ✅ `os.path` |
| 空列表 | `list()` | **`[]` · 77 处 / 22 文件** | ✅ `[]` |
| 目录创建 | `os.makedirs(exist_ok=True)` | ✅ **13 处符合** | ✅ 一致 |
| 日志 | 统一 `print` | **引擎/核心用 `logging`**（`logging_setup.py`）；`print` 集中在 `tools/` | ✅ 分场景 |

**`os.path.join` 用量最多的文件**：

```
installer/installer.py    26
app/diag_startup.py        8
tools/test_engines.py      7
app/core/logging_setup.py  6
app/first_run.py           6
```

---

## 三、格式：**双引号、行长宽松、无文件头**

| 项 | 常见规范 | **原作者实际** | 采用 |
|---|---|---|---|
| 字符串引号 | 单引号 | **双引号 312 处**；单引号仅 23 处 | ✅ **双引号** |
| 行长 | ≤ 80 | **> 80 共 371 处 / 34 文件** | ✅ 宽松（长文案不拆） |
| 文件头 | Founded / @author | **0 处有** | ✅ 不标 |
| 文件行数 | ≤ 1000 | ✅ **0 个超限**（最大 857） | ✅ 符合 |

**行长超标的分布**（多为长文案，拆开更难读）：

| 文件 | > 80 处数 | 最长行 |
|---|---|---|
| `app/core/i18n.py` | 53 | **500** |
| `app/core/benchmark.py` | 35 | 100 |
| `app/ui/main_window.py` | 26 | 111 |
| `app/core/aigc_rules.py` | 24 | 189 |
| `installer/installer.py` | 23 | 110 |

**判断**：91 处 >100 字符的行，绝大多数是 `desc` / `desc_en` / i18n 文案等
**长字符串**，不是"逻辑被压缩在一行"。

---

## 四、命名与结构

| 项 | 常见规范 | **原作者实际** | 采用 |
|---|---|---|---|
| 单字母变量 | 禁止 | **71 处**（`i` / `d` / `k` 等） | ✅ 允许 |
| 变量名长度 | ≤ 20 字符 | ✅ **仅 1 处超限** | ✅ 符合 |
| 目录结构 | `src/` + `config/` | **无 `src/`、无 `config/`** | ✅ 见下表 |

**实际目录结构**：

```
app/
├── main.py                 入口
├── first_run.py            首次启动引导
├── diag_startup.py         自检
├── core/                   核心逻辑（16 个 .py）
│   └── engines/            引擎实现（10 个 .py）+ registry 注册表
└── ui/                     界面（7 个 .py）+ glass.py 设计系统
installer/                  安装器（1 个 .py）
tools/                      测试与辅助脚本（4 个 .py）
```

**架构特点**（设计得不错，值得保持）：
- `core/engines/registry.py` —— 引擎注册表 + 插件机制（`@register("impl")`）
- `core/engines/catalog.py` —— 引擎清单，与实现解耦，改清单即可换模型
- `core/engines/manager.py` —— 多层清单合并（内置 < 远端 < 本地覆盖 < 用户）
- `ui/glass.py` —— 统一设计令牌

---

## 五、逐项对照总表

| # | 项 | 通行规范 | **原作者风格** | 一致? |
|---|---|---|---|---|
| 1 | 注释语言 | 英文 | **中文** | ❌ |
| 2 | docstring | 英文 | **中文** | ❌ |
| 3 | 异常消息 | 英文 | **中文** | ❌ |
| 4 | 路径构造 | pathlib | **`os.path.join`** | ❌ |
| 5 | 空列表 | `list()` | **`[]`** | ❌ |
| 6 | 引号 | 单引号 | **双引号** | ❌ |
| 7 | 行长 | ≤ 80 | **宽松** | ❌ |
| 8 | 文件头 | Founded/@author | **无** | ❌ |
| 9 | 目录结构 | `src/`+`config/` | **`app/core`+`app/ui`** | ❌ |
| 10 | 日志 | 统一 print | **核心 logging / 工具 print** | ⚠️ 分场景 |
| 11 | `makedirs(exist_ok=True)` | 要求 | ✅ 一致 | ✅ |
| 12 | 文件行数 ≤1000 | 要求 | ✅ 符合 | ✅ |
| 13 | 变量 ≤20 字符 | 要求 | ✅ 符合 | ✅ |

**13 项中，9 项与通行规范相反，2 项一致，2 项分场景。**

---

## 六、本次改动的一致性核对

对 11 个改动文件做了逐项核验（数据：`docs/calibration.md` §3.3）：

| 文件 | 原作者 >80 占比 | 我新增行 >80 占比 | 编码声明 | 判断 |
|---|---|---|---|---|
| `app/core/cluster.py` | 3% | 0% | 保持无 | ✅ |
| `app/core/engines/base.py` | 4% | 3% | 保持有 | ✅ |
| `app/core/engines/binoculars_engine.py` | 4% | 0% | 保持有 | ✅ |
| `app/core/engines/catalog.py` | 12% | 14%（2 行长文案） | 保持有 | ✅ |
| `app/core/engines/curvature_engine.py` | 6% | 4% | 保持有 | ✅ |
| `app/core/engines/perplexity_engine.py` | 0% | 0% | 保持有 | ✅ |
| `app/core/report.py` | 11% | 0% | 保持无 | ✅ |
| `app/ui/engine_dialog.py` | 6% | 4% | 保持有 | ✅ |
| `app/ui/main_window.py` | 4% | 0% | 保持无 | ✅ |
| `app/ui/settings_dialog.py` | 5% | 0% | 保持有 | ✅ |
| `tools/smoke_test.py` | 3% | 1 行 100 字符 | 保持有 | ⚠️ 可接受 |

**结论：改动未混入外部规范风格。**

---

## 七、复核方法

```
# 扫描原作者风格（只读 git 已跟踪文件）
python tools/audit_probes.py --only style_report
# 输出到控制台（不再落盘）

# 核对改动是否一致
python tools/audit_probes.py --only style_report
# 输出到控制台
```
