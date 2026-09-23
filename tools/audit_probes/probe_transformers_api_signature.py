# -*- coding: utf-8 -*-
"""探针 v5：transformers 5.17 对项目 API 的兼容性（不下载模型）。"""
import io
import inspect
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"d:\Project\AIGC\app")

print("=" * 68)
print("【4.1】transformers 5.17 兼容性探针（不下载模型）")
print("=" * 68)

import transformers  # noqa: E402

print("transformers 版本 = %s" % transformers.__version__)
try:
    import huggingface_hub

    print("huggingface_hub 版本 = %s" % huggingface_hub.__version__)
except Exception as e:
    print("hub 探测失败: %s" % e)
import torch  # noqa: E402

print("torch = %s, cuda = %s" % (torch.__version__, torch.cuda.is_available()))
print()

ok_all = True


def chk(label, fn):
    global ok_all
    try:
        v = fn()
        print("   OK      %s" % label)
        return v
    except Exception as e:
        ok_all = False
        print("   FAIL    %s -> %s: %s" % (label, type(e).__name__, e))
        return None


print("A) 项目实际用到的类是否存在（base.py:124-129 的 loaders 字典）")
chk("AutoTokenizer", lambda: transformers.AutoTokenizer)
chk("AutoModelForSequenceClassification",
    lambda: transformers.AutoModelForSequenceClassification)
chk("AutoModelForCausalLM", lambda: transformers.AutoModelForCausalLM)
chk("AutoModelForSeq2SeqLM", lambda: transformers.AutoModelForSeq2SeqLM)
print()

print("B) base.py:106 的调用签名是否仍受支持")
chk("from_pretrained(cache_dir=...)", lambda: transformers.AutoModelForCausalLM
    .from_pretrained.__doc__)
sig = inspect.signature(transformers.AutoModelForCausalLM.from_pretrained)
params = list(sig.parameters)
print("      from_pretrained 参数: %r" % params[:14])
for need in ("cache_dir", "local_files_only"):
    if need in params:
        print("      OK      from_pretrained 支持 %s" % need)
    else:
        ok_all = False
        print("      FAIL    from_pretrained 不支持 %s" % need)
print()

print("C) simpleai_engine.py:38 的 tokenizer 调用签名")
t = chk("AutoTokenizer.from_pretrained 可获取", lambda: transformers.AutoTokenizer
        .from_pretrained)
if t:
    ps = list(inspect.signature(transformers.AutoTokenizer.from_pretrained).parameters)
    print("      AutoTokenizer.from_pretrained 参数: %r" % ps[:12])
print()

print("D) curvature_engine.py:118 的 generate 关键字")
chk("GenerationMixin.generate", lambda: transformers.GenerationMixin.generate)
gs = list(inspect.signature(transformers.GenerationMixin.generate).parameters)
print("      generate 参数(前 20): %r" % gs[:20])
for need in ("do_sample", "top_p", "temperature", "max_new_tokens", "pad_token_id"):
    if need in gs:
        print("      OK      generate 支持 %s" % need)
    else:
        ok_all = False
        print("      FAIL    generate 不支持 %s" % need)
print()

print("E) 项目引擎模块能否在本环境成功导入（TORCH_OK / MODULE_ERRORS）")
import core.engines as eng  # noqa: E402

print("      TORCH_OK    = %s" % eng.TORCH_OK)
print("      TORCH_ERROR = %r" % eng.TORCH_ERROR)
print("      MODULE_ERRORS = %r" % eng.MODULE_ERRORS)
print("      registered() = %r" % eng.registered())
if eng.MODULE_ERRORS:
    ok_all = False
print()

print("F) 引擎能否实例化并解析模型清单（不加载权重）")
from core.engines import catalog, create_engine  # noqa: E402

for eid in ("simpleai", "gltr", "fastdetectgpt", "detectgpt", "binoculars"):
    try:
        e = create_engine(catalog.by_id(eid), r"d:\Project\AIGC\app")
        print("      OK      %-14s repos=%r" % (eid, e.repos()))
    except Exception as ex:
        ok_all = False
        print("      FAIL    %-14s %s: %s" % (eid, type(ex).__name__, ex))
print()

print("G) 真加载 tokenizer（联网下载 ~1MB，走 hf-mirror）")
print("      [跳过] 本探针不下载任何文件")
print()
print(">>> 结论: %s" % ("API 层完全兼容" if ok_all else "存在不兼容项，见上方 FAIL"))
