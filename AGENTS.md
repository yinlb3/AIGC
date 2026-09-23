# AGENTS.md

## 作者

- **原作者**：gxgx3456（gxgx3456@qq.com）
- **本次改动**：yinlb（yinlb3@foxmail.com），受原作者委托的代码审查与修复（2026-09）

## 本次改动的目的

修复会影响用户使用效果的缺陷，**让代码真正实现原作者的设计意图**。

不改架构、不加功能、不动原作者的文档。

## 边界（改动前必读）

### 一律不改

| 对象 | 说明 |
|---|---|
| `README.md`、`README.en.md`、`使用手册.md`、`CHANGELOG.md` | 原作者文档。待修订内容记在 `docs/DOC_FIXES_PENDING.md` |
| 目录结构 | `app/core` + `app/ui` + `installer/` + `tools/`，不要引入 `src/` 或 `config/` |
| 引擎注册机制 | `registry.py` 的 `@register` + `catalog.py` 清单分离设计 |
| 界面设计系统 | `ui/glass.py` 的设计令牌 |

### 只修 bug，不加功能

拿不准的先问。例：曾给 gltr 加过论文的 Test-2 算法（`gltr_buckets()`），
因属"换算法"而非"修缺陷"，已回退。

### 判据：是否影响用户使用效果

**影响就修，不影响就不动。** 例：

- 修：Binoculars 公式错（导致恒判 AI）、显存不足静默降速、中文超长文本崩溃
- 不修：行长 371 处超标、缺编码声明 14 个文件

## 代码风格：跟随原作者

**本项目风格有意偏离通行规范，不要"修正"它。** 详见 `docs/AUTHOR_STYLE.md`。

| 项 | 本项目做法 |
|---|---|
| 注释 / docstring / 异常消息 | **中文**（与通行规范相反） |
| 路径构造 | `os.path.join()`，不引入 pathlib |
| 字符串引号 | **双引号** |
| 空列表 | `[]`，不改成 `list()` |
| 行长 | **不限**（长文案拆开更难读） |
| 文件头 | 不加 Founded / @author |
| 编码声明 | 保持现状，不统一 |

## 改完必须跑回归

```powershell
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\smoke_test.py        # 10/10
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\test_engines.py      # 13/13
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\test_detect.py
C:\ProgramData\miniconda3\envs\pytorch\python.exe tools\fusion_selftest.py
```

## 环境要点

- 依赖环境：`C:\ProgramData\miniconda3\envs\pytorch`（torch 2.8.0+cu129 / transformers 5.17.0）
- 模型缓存：`settings.json` 的 `download.models_dir`（当前 `D:\hf_cache\aigc_models`）
- 下载走镜像：`$env:HF_ENDPOINT='https://hf-mirror.com'`
- **坑**：残留 `HF_HUB_OFFLINE=1` 会让下载报 "outgoing traffic disabled"

## 长任务必须带进度

```python
def prog(done, total):
    print("[%d/%d] %.0f%%" % (done, total, done * 100.0 / total), flush=True)
    #                                        flush 必须加，否则输出被缓冲

eng.predict_paragraphs(texts, dev, progress_cb=prog, **params)
```

跑全量前先用 3~5 条测单条耗时；预估超 30 分钟先报告，别闷头跑。

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/AUTHOR_STYLE.md` | 原作者风格 13 项实测对照（改动前必读） |
| `docs/AUDIT_2026-09-22.md` | 19 条 bug 的定位与修复、TODO |
| `docs/PAPER_GAPS.md` | 与所引论文的差异清单 |
| `docs/DOC_FIXES_PENDING.md` | 原作者文档的待修订清单（暂不改） |
| `docs/HANDOFF.md` | 交接说明 |
