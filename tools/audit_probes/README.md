# 审查探针脚本（2026-09-22）

这批脚本用于验证 2026-09-22 那次代码审查发现的 bug。
每个脚本**只读**项目源码，不修改任何项目文件，输出全部打印到控制台。

## 运行方式

```powershell
# 用装有 torch / transformers / PySide6 的解释器
$env:PYTHONIOENCODING='utf-8'
& 'C:\ProgramData\miniconda3\envs\pytorch\python.exe' tools\audit_probes\probe_binoculars_engine_math.py
```

脚本内部已自带 `sys.path.insert(项目/app)`，无需额外设 PYTHONPATH。

## 脚本清单

| 脚本 | 验证内容 | 手法 |
|---|---|---|
| probe_binoculars_engine_math.py | Binoculars 公式恒判 AI、降重格式化、hf_endpoint 写入 | 复刻项目算术式代入真实量级 |
| probe_cluster_port_and_logprob_chunk.py | 集群端口绑定、avg_logprob 分块口径 | 真起 socket、桩 model 返回可预测 loss |
| probe_style_loop_and_param_merge.py | _style_fix 死循环、参数覆盖顺序 | 遍历规则表 + 纯 dict 合并 |
| probe_license_i18n_report_escape.py | license 空壳、i18n 拼接键、报告转义 | 真调 License.activate、真查词典 |
| probe_static_scan_ast.py | 静态扫描 | ast 解析全部 .py 找未用导入/行长/静默 except |
| probe_transformers_api_signature.py | transformers API 存在性 | inspect.signature（**有误报**，见下） |
| probe_transformers_real_call.py | 同上，排除上一条的误报 | 真调用 from_pretrained / generate（本地随机权重） |
| probe_report_html_render.py | 报告注入的真实危害 | 离屏 Qt 真渲染 HTML |
| probe_cluster_discovery_chain.py | 集群发现失效根因 | 真起 master + worker，抓端口绑定竞争 |
| probe_gui_offscreen_runtime.py | 主窗口 / 设置对话框离线复现 | 离屏实例化 MainWindow、SettingsDialog |
| probe_author_style.py | **原作者代码风格逐项调查** | 按常见规范逐项统计原作者实际做法，输出 `docs/calibration/author_style.txt` |
| probe_style_check.py | **原作者代码格式检查** | 行长 / 缩进 / 裸 except / 可变默认参数等 10 项，输出 `docs/calibration/style_check.txt` |
| probe_style_diff.py | **改动与原作者风格的一致性核对** | 对比我新增行与原作者原有行的行长分布、编码声明，输出 `docs/calibration/style_diff.txt` |

## 重要提示

**probe_transformers_api_signature.py 的输出不可信**：`inspect.signature`
对 `from_pretrained(**kwargs)` 这类签名无法看到真实形参，会误报
「不支持 cache_dir / do_sample」。判断兼容性请以
**probe_transformers_real_call.py 的真调用结果** 为准 —— 后者已证明
这些参数全部可用。

**Qt 相关脚本需要离屏环境**：脚本内已设
`os.environ["QT_QPA_PLATFORM"] = "offscreen"`，不会弹出窗口。
运行时会打印 `QFontDatabase: Cannot find font directory` 警告，属正常，可忽略。

**probe_cluster_discovery_chain.py 会占用 UDP 47650 / TCP 47651 约 10 秒**，
跑完自动释放。

## 写操作说明

| 脚本 | 写盘行为 |
|---|---|
| probe_binoculars_engine_math.py | 无 |
| probe_cluster_port_and_logprob_chunk.py | 无 |
| probe_style_loop_and_param_merge.py | 无 |
| probe_license_i18n_report_escape.py | 系统临时目录建 `aigc_lic_*` 写 license.key，跑完自清理 |
| probe_static_scan_ast.py | 无 |
| probe_transformers_api_signature.py | 无 |
| probe_transformers_real_call.py | 无（本地随机权重模型，不联网不落盘） |
| probe_report_html_render.py | 无 |
| probe_cluster_discovery_chain.py | 无 |
| probe_gui_offscreen_runtime.py | 系统临时目录建 `aigc_gui_*` 写 settings.json（避开项目内文件） |
