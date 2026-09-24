# 检测流程（改完代码按此顺序过一遍）

- 目的：把「凭印象查局部」改成**穷举检查**
- 用法：依次执行，**每步看全部输出**，不能只扫最后一行

---

## 一、范围（不许凭印象缩小）

**恒为以下全部**，与"这次改了哪些文件"无关：

| 范围 | 含 |
|---|---|
| 代码 | `app/`、`installer/`、`tools/`（含 `tools/probes/`）|
| 文档 | `AGENTS.md`、`docs/*.md` |
| 配置 | `pyrightconfig.json`、`.gitignore`、`settings.json`（不入库的也要核）|

当初订立本流程的原因：只查了 `tools/probes/` 就宣布"pyright 0 errors"，
而 `installer/`（导入根不同）与 `tools/smoke_test.py` 里各有警告 —— 靠用户截图才发现。

---

## 二、五个检测层（从快到慢）

### 第 1 层：静态检查（秒级）

```powershell
npx --yes pyright                 # 全仓库，期望 0 errors
```

- **必须全仓库**（指定文件会漏掉别的目录）
- `pyrightconfig.json` 的 `extraPaths` 要覆盖**全部导入根**：`app/`（`core.*`、`ui.*`）与
  `app/core/`（`i18n`、`netfix` 裸模块名，installer 用）
- 刻意保留的 `reportUnusedImport` 用**单行** `# pyright: ignore[reportUnusedImport]`；
  在缩进里写 `# pyright: reportX=false` 是 file-level 语法，会直接报错

### 第 2 层：自带回归（分钟级）

```powershell
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\smoke_test.py      # 10/10
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\test_engines.py    # 13/13
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\test_detect.py
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\fusion_selftest.py
```

**覆盖率有限**（不测 UI 端到端、不测 installer）—— 全绿是必要不充分条件。

### 第 3 层：探针（按改动面选）

```powershell
... tools\audit_probes.py                      # safe 组
... tools\audit_probes.py --only ui_flow       # 改过界面
... tools\audit_probes.py --only package_flow  # 改过 installer / 发布
... tools\audit_probes.py --only env_setup     # 改过 installer / 首次启动 / 卸载器
... tools\audit_probes.py --only ui_config     # 改过配置
```

### 第 4 层：端到端真跑（最容易被跳过）

**"数据要从 A 流到 B"的改动必须真跑整条链路**，不能只验到中间层：

| 链路 | 怎么验 |
|---|---|
| 引擎 → 界面报告 | 真建 `DetectWorker`、`start()`、等 `finished_ok`，**读信号里每一项** |
| 设置往返 | `SettingsDialog._save()` → 重读 `Settings` 比对 |
| 检测 → 降重 | `RewriteDialog._recheck()` 返回 probs |
| 装机 → 程序可跑 | 静态核查（真装写注册表）；**改了源码先重打包**，否则装出去是旧 exe |

教训：曾只调 `engine.predict_paragraphs()` 就宣布"四档已通"，而真正跑检测的是
`detect_local` 内部另建的实例 —— 中间隔了一层，只验两端发现不了。

### 第 5 层：有副作用的部分（静态核查）

不能真跑的（写注册表、`rmtree`、联网下载）：

- 装机：必需文件齐否、新增数据文件是否在 `app/` 内（随 `copytree` 分发）、installer 零依赖、卸载器清得干净
- 打包：`tools/build_exe.ps1` 三步（顺序不可反）—— 安装器装的是 **exe 内嵌的快照**，
  改了源码不重打等于没改；产物 `build_info.json` 带版本 + git 短哈希，装完日志首行可核对

---

## 三、边界与异常输入

每个新增的展示 / 转换函数都要过一遍：

| 场景 | 期望 |
|---|---|
| 入参为 `None` | 不崩、不显示空行 |
| 空集合 / 全 0 | 不崩、不显示误导性内容 |
| 长度不匹配 | 不越界 |
| 含特殊字符 | 已转义 |
| 数值展示 | **各项之和自洽**（如四档占比恰为 100%）|

教训：四档各自 `round()` 后和可能是 99%/101%（3000 例中 1014 例），已改最大余数法。

---

## 四、i18n（改了界面文案必查）

- 新文案**必须同时进 `i18n.py` 的 `ZH` 与 `EN`**
- 切语言跑一遍看有无中文残留；`smoke_test` 只查键存在，**查不出硬编码中文**

---

## 五、收尾（三件）

1. **清临时文件 / 进程**：自己在 `%TEMP%` 产生的文件、遗留的 `python.exe` 与外部窗口（只清自己启动的）
2. **查 BOM**：`.py` 要**无** BOM（`ast.parse` 会失败）；`.ps1` 含中文注释则要**有** BOM
   （全英文注释则不必）。PS 5.1 的 `Set-Content -Encoding UTF8` 会写 BOM，写 json 请用
   `[IO.File]::WriteAllText($p, $s, (New-Object Text.UTF8Encoding($false)))`。
   查法：`tools/audit_probes.py --only static_scan` 的 `【3.0】`
3. **文档同步**：改动是否反映到 `FIXES.md` / `CALIBRATION.md` / `HANDOFF.md` / `AGENTS.md`，
   并顺手清理过时内容

---

## 六、盲区（自己查不到，必须问用户）

| 盲区 | 为什么要问 |
|---|---|
| IDE 的「问题」面板 | Pylance 诊断与 CLI `pyright` 不完全一致 |
| 真机界面长相 | 只能 Qt 离屏构造，看不到真实排版 / 遮挡 |
| 装机后的实际运行 | 不能真装（写注册表）；改完请用户装一次验证 |
| 进度条刷新粒度 | 只能轮询进度文件，看不到实际刷新 |

**处理方式**：主动请用户看一眼或截图，比自己猜快得多。

