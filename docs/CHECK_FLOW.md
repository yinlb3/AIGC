# 检测流程（改完代码按此顺序过一遍）

- 目的：把「凭印象查局部」改成「**穷举检查**」，避免漏项
- 用法：每轮改完代码依次执行，**每步都要看全部输出**，不能只扫最后一行

---

## 一、范围（关键：不许凭印象缩小）

**检查范围恒为以下全部**，与"我这次改了哪些文件"无关：

| 范围 | 含 |
|---|---|
| 代码 | `app/`、`installer/`、`tools/`（**含 `tools/probes/`**）|
| 文档 | `AGENTS.md`、`docs/*.md` |
| 配置 | `pyrightconfig.json`、`.gitignore`、`settings.json`（不入库的也要核） |

**教训**：本流程订立的直接原因 —— 曾只查 `tools/probes/` 就宣布
「pyright 0 errors」，而 `installer/`（导入根不同）与 `tools/smoke_test.py`
里各有警告，**靠用户截图才发现**。

---

## 二、五个检测层（从快到慢，逐层穷举）

### 第 1 层：静态检查（秒级，先跑）

```powershell
npx --yes pyright                 # 全仓库，期望 0 errors
```

- **必须全仓库**，不指定文件（指定文件会漏掉别的目录）
- `pyrightconfig.json` 的 `extraPaths` 须覆盖**全部导入根**：
  本项目有 **3 个** —— `app/`（`core.*` / `ui.*`）、`app/core/`（`i18n` /
  `netfix` 裸模块名，installer 用）、以及运行时注入的路径
- 剩余的 `reportUnusedImport` 若是**刻意的**（如 smoke_test 的"导入即测试"），
  用**单行** `# pyright: ignore[reportUnusedImport]` 抑制 ——
  **不要在缩进里写 `# pyright: reportX=false`**，那是 file-level 语法，会直接报错

### 第 2 层：自带回归（分钟级）

```powershell
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\smoke_test.py      # 10/10
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\test_engines.py    # 13/13
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\test_detect.py
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\fusion_selftest.py
```

**注意**：这些脚本**覆盖率有限**（不测 UI 端到端、不测 installer），
全绿**不代表没问题**。它们只是必要不充分条件。

### 第 3 层：探针（可选，按改动面选）

```powershell
... tools\audit_probes.py                 # safe 组
... tools\audit_probes.py --only ui_flow          # 改过界面
... tools\audit_probes.py --only package_flow     # 改过 installer / 发布
... tools\audit_probes.py --only env_setup        # 改过 installer / 首次启动 / 卸载器
... tools\audit_probes.py --only ui_config        # 改过配置
```

### 第 4 层：**端到端真跑**（关键，最容易被跳过）

**凡是"数据要从 A 流到 B"的改动，必须真跑整条链路**，不能只验到中间层。

本项目已验证的端到端路径（各写一次真实调用）：

| 链路 | 怎么验 |
|---|---|
| 引擎 → 界面报告 | 真建 `DetectWorker`、`start()`、等 `finished_ok`，**读信号里的每一项** |
| 设置往返 | `SettingsDialog._save()` → 重读 `Settings` 比对 |
| 检测 → 降重 | `RewriteDialog._recheck()` 返回 probs |
| 装机 → 程序可跑 | 静态核查（真装会写注册表，见第 5 层）；**改了源码先重打包**（见 `AGENTS.md`「发布打包」），否则装出去的是旧 exe |

**教训**：曾只调 `engine.predict_paragraphs()` 就宣布"四档已通"，
而**真正跑检测的是 `detect_local` 内部另建的实例**，界面拿到的永远是
`None` —— 中间隔了一层，只验两端就发现不了。

### 第 5 层：静态核查有副作用的部分

不能真跑的操作（写注册表、`rmtree`、联网下载），用**静态核查**代替：

- 装机：必需文件是否齐、**新增数据文件是否在 `app/` 内**（随 `copytree` 分发）、
  installer 是否零依赖、卸载器是否清干净
- 见 `tools/probes/package_flow.py`
- **打包**：`tools/build_exe.ps1` 三步（顺序不可反）→ 安装器装的是**exe 内嵌的快照**，
  **改了源码不重打等于没改**（2026-09-24 实测：装出去的是 5 天前的包）；产物里
  `build_info.json` 带版本 + git 短哈希，装完日志首行可核对

---

## 三、边界与异常输入（专治"只测正常路径"）

**每个新增的展示/转换函数都要过一遍**：

| 场景 | 期望 |
|---|---|
| 入参为 `None` | 不崩、不显示空行 |
| 入参为空集合 / 全 0 | 不崩、不显示误导性内容 |
| 长度不匹配（短于主列表）| 不越界 |
| 含特殊字符 | 已转义 |
| **数值展示** | **各项之和须自洽**（如四档占比要恰为 100%，见 `_pct100`）|

**教训**：四档各自 `round()` 后和可能是 99%/101%（实测 3000 例中 1014 例），
用户相加核对会以为程序算错 —— 已改最大余数法。

---

## 四、i18n 一致性（改了界面文案必查）

- 新增文案**必须同时进 `i18n.py` 的 `ZH` 与 `EN`**
- 查法：切语言跑一遍，看有无中文残留
- `smoke_test.py` 的「i18n 键完整性」只查**键存在**，不查**是否硬编码**，
  所以硬编码中文它发现不了

**教训**：四档文案曾硬编码中文，英文界面会串中文。

---

## 五、收尾（三件必做）

1. **清临时文件/进程**：`%TEMP%` 下自己产生的文件与目录、遗留的
   `python.exe` / 外部窗口（**只清自己启动的**，见 skill 的进程清理条目）
- **查 BOM**：PowerShell 批量改过文件后，读首 3 字节是否为 `EF BB BF`。
  **只对 `.py` 要求无 BOM**（`ast.parse` 会失败）；
  **`.ps1` 反而需要 BOM**（否则 PowerShell 5.1 按 GBK 读，中文注释报语法错）
  —— 若 `.ps1` **全用英文注释**则不必带 BOM（`tools/build_exe.ps1` 即如此）。
  另外 PS 5.1 的 `Set-Content -Encoding UTF8` **会写 BOM**，写 json 要用
  `[IO.File]::WriteAllText($p, $s, (New-Object Text.UTF8Encoding($false)))`，
  否则 `json.load` 直接抛、静默退化成默认值（`build_info` 踩过）。
  查法：`tools/audit_probes.py --only static_scan` 的 `【3.0】`（只扫 `.py`）
3. **文档同步**：改动是否已反映到 `FIXES.md`（缺陷/待办）、
   `CALIBRATION.md`（数据）、`HANDOFF.md`（状态）、`AGENTS.md`（约定）；
   **顺便查旧内容是否过时**（如探针数量、已修的 TODO 还在不在）

---

## 六、盲区（自己查不到，必须问用户）

| 盲区 | 为什么要问 |
|---|---|
| **IDE 的「问题」面板** | Pylance 的诊断与 CLI 的 `pyright` 不完全一致 |
| **真机界面长相** | 只能 Qt 离屏构造，看不到真实排版/遮挡 |
| **装机后的实际运行** | 不能真装（写注册表）。2026-09-24 晚改完卸载器 exe 后，需用户装一次验证：装完自动关闭、日志首行构建信息、`uninstaller.exe` 落地、控制面板卸载指向它 —— 见 `FIXES.md` §3 第 4 项 |
| **用户看到的进度条刷新** | 我只能轮询进度文件，看不到刷新粒度 |

**处理方式**：这几类**主动请用户看一眼或截图**，比自己猜快得多。
