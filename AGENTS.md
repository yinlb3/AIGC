# AGENTS.md

## 作者

- 原作者：gxgx3456（gxgx3456@qq.com）
- 本次改动：yinlb（yinlb3@foxmail.com），受委托的审查与修复（2026-09）

## 目的

修影响用户使用效果的缺陷。**不改架构、不换作者的实现方式、不动他的文档。**

## 边界

### 不改

| 对象 | 说明 |
|---|---|
| `README.md` / `README.en.md` / `使用手册.md` / `CHANGELOG.md` | 原作者文档；待修订记入 `docs/FIXES.md` |
| 目录结构 | `app/core` + `app/ui` + `installer/` + `tools/`，不引入 `src/`、`config/` |
| 已实现的形式 | 作者用 A 方式做的，不因"B 更简洁"而换 —— 除非 A 有缺陷 |

**但要分清**：补 bug、补缺失功能属于本职，该改就改。
曾经的误解是"一个字都不能碰"，导致什么都修不了。

### 判据：影响用户使用效果吗

- 修：Binoculars 公式错（恒判 AI）、显存不足静默降速、中文长文本崩溃
- 不修：行长超标、缺编码声明（属有意风格）

## 代码风格：跟随原作者

**本项目风格有意偏离通行规范，不要"修正"。** 详见 `docs/AUTHOR_STYLE.md`。

| 项 | 做法 |
|---|---|
| 注释 / docstring / 异常消息 | 中文 |
| 路径构造 | `os.path.join()`，不用 pathlib |
| 引号 | 双引号 |
| 空列表 | `[]` |
| 行长 | 不限 |
| 文件头 | 不加 Founded / @author |
| 编码声明 | 保持现状 |

### 文档要简洁

**所有文档（含本文件）都短。** 只写怎么做和为什么，不写过程、不重复。

## 标定值必须外置

阈值等标定值**不写死在 `catalog.py`**，而是：

```
tools/ 标定探针 → python tools/export_calibration.py → app/core/engines/engines_calibration.json
                                                              ↓ 启动时读取覆盖
                                                       manager.py
```

优先级：`catalog.py 出厂值 < 标定值 < 远端 < 用户覆盖`

- 改动后跑 `python tools/export_calibration.py --audit` 查有无漏网的硬编码
- 放 `app/` 内才能随安装器（`copytree`）分发到用户机器

## 提交规约

Conventional Commits 1.0.0：`type: 简述`，英文、祈使句、每行 ≤72 字符。

消息写入仓库外，`-F` 传入后删除：

```powershell
$msg = Join-Path $env:TEMP "aigc_commit_msg.txt"   # 写入消息（UTF-8）
git commit -F $msg
Remove-Item $msg
```

禁止在仓库内建临时文件；提交前用 `git status` 核对，不用 `git add -A`。

## 改完必须跑回归

```powershell
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\smoke_test.py        # 10/10
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\test_engines.py      # 13/13
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\test_detect.py
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\fusion_selftest.py
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\audit_probes.py      # safe 组
```

装机 / 界面 / 配置改动时另跑（详见 `docs/FIXES.md` §6）：

```powershell
... tools\audit_probes.py --only package_flow   # 装机必需文件、标定数据位置、零依赖
... tools\audit_probes.py --only ui_flow        # 界面真跑一次检测
... tools\audit_probes.py --only ui_config      # 默认值合理性
```

## 静态检查

`npx --yes pyright`（期望 0 errors）；它能抓出 heavy 组探针里的未定义名、重复定义等"从没跑过所以没人发现"的错。

**改完代码按 `docs/CHECK_FLOW.md` 的五层检测流程过一遍**（穷举范围，不许只查改过的文件）。


## 环境

- 依赖：`C:\ProgramData\miniconda3\envs\pytorch`（torch 2.8.0+cu129 / transformers 5.17.0）
- 模型缓存：`settings.json` 的 `download.models_dir`
- 下载走镜像：`$env:HF_ENDPOINT='https://hf-mirror.com'`
- 坑：残留 `HF_HUB_OFFLINE=1` 会让下载报 "outgoing traffic disabled"

## 长任务带进度

`print(..., flush=True)` —— **flush 必须加**，否则输出被缓冲。
跑全量前先用 3~5 条测单条耗时；预估超 30 分钟先报告。

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/AUTHOR_STYLE.md` | 原作者风格对照（改动前必读） |
| `docs/FIXES.md` | bug 定位与修复、TODO 状态 |
| `docs/FIXES.md §2` | 与论文的差异 |
| `docs/FIXES.md` | 原作者文档待修订项（暂不改） |
| `docs/CALIBRATION.md` | 标定数据 / 阈值依据 |
| `docs/CHECK_FLOW.md` | **改完代码的五层检测流程**（穷举范围 + 边界 + i18n + 盲区）|
| `docs/HANDOFF.md` | 交接说明 |
| `tools/audit_probes.py` | 可复现探针（`--list`） |
| `tools/prepare_datasets.py` | 数据集加载（内存处理，不落盘） |
| `tools/export_calibration.py` | 导出标定值（`--audit` 查漏） |

