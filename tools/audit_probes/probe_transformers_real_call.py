# -*- coding: utf-8 -*-
"""探针 v6：甄别 v5 的 B/D 两处 FAIL 是签名穿透误报还是真不兼容。"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"d:\Project\AIGC\app")

import transformers  # noqa: E402

print("=" * 68)
print("【4.1b】真调用验证（不下载任何文件）")
print("=" * 68)
print("transformers %s" % transformers.__version__)
print()

print("A) from_pretrained(**kwargs) 签名 —— 用 help 文本核对真实形参")
doc = transformers.AutoModelForCausalLM.from_pretrained.__doc__ or ""
for kw in ("cache_dir", "local_files_only", "torch_dtype", "dtype", "device_map"):
    print("      文档提及 %-18s : %s" % (kw, kw in doc))
print()

print("B) 真调用：故意传不存在的仓库名 + 不存在的参数，看报什么错")
print("   若参数不被接受 -> TypeError/ValueError('unexpected keyword')")
print("   若参数被接受 -> 报仓库不存在/网络错误")
print()

cases = [
    ("cache_dir + local_files_only（base.py:106 的写法）",
     dict(cache_dir=r"d:\Project\AIGC\app\models\probe", local_files_only=True)),
    ("torch_dtype（老写法）", dict(torch_dtype="auto", local_files_only=True)),
    ("dtype（新写法）", dict(dtype="auto", local_files_only=True)),
]
for label, kw in cases:
    kw = dict(kw)
    try:
        transformers.AutoModelForCausalLM.from_pretrained(
            "___definitely_not_a_real_repo___", **kw)
        print("   UNEXPECTED OK   %s" % label)
    except TypeError as e:
        print("   TypeError   %s -> %s" % (label, e))
    except Exception as e:
        msg = str(e)[:110].replace("\n", " ")
        print("   已接受参数  %s -> %s: %s" % (label, type(e).__name__, msg))
print()

print("C) AutoTokenizer 同样测试")
try:
    transformers.AutoTokenizer.from_pretrained(
        "___definitely_not_a_real_repo___",
        cache_dir=r"d:\Project\AIGC\app\models\probe", local_files_only=True)
except TypeError as e:
    print("   TypeError -> %s" % e)
except Exception as e:
    print("   已接受参数 -> %s: %s" % (type(e).__name__, str(e)[:110].replace("\n", " ")))
print()

print("D) generate 关键字：用 generate 的 docstring 与 GenerationConfig 核对")
gdoc = transformers.GenerationMixin.generate.__doc__ or ""
for kw in ("do_sample", "top_p", "temperature", "max_new_tokens", "pad_token_id"):
    print("      generate 文档提及 %-16s : %s" % (kw, kw in gdoc))
try:
    from transformers import GenerationConfig

    gc = GenerationConfig()
    have = gc.to_dict()
    print()
    print("      GenerationConfig 实际字段:")
    for kw in ("do_sample", "top_p", "temperature", "max_new_tokens",
               "pad_token_id", "top_k", "num_beams"):
        print("         %-16s = %r" % (kw, have.get(kw, "<缺失>")))
except Exception as e:
    print("      GenerationConfig 探测失败: %s" % e)
print()

print("E) 用极小本地模型真跑 generate（不联网，纯随机权重）")
try:
    from transformers import GPT2Config, GPT2LMHeadModel

    cfg = GPT2Config(vocab_size=99, n_positions=64, n_embd=32, n_layer=1, n_head=1)
    m = GPT2LMHeadModel(cfg)
    import torch

    ids = torch.randint(1, 90, (1, 8))
    out = m.generate(ids, do_sample=True, top_p=0.96, temperature=1.0,
                     max_new_tokens=4, pad_token_id=0)
    print("   OK  generate(do_sample/top_p/temperature/max_new_tokens/pad_token_id)")
    print("       输出形状 = %r" % (tuple(out.shape),))
except TypeError as e:
    print("   FAIL TypeError -> %s" % e)
except Exception as e:
    print("   FAIL %s: %s" % (type(e).__name__, str(e)[:160]))
print()

print("F) 用极小本地模型真跑 base.avg_logprob（不联网）")
sys.path.insert(0, r"d:\Project\AIGC\app")
from core.engines.base import BaseEngine  # noqa: E402


class Probe(BaseEngine):
    impl = "probe"
    needs_torch = False

    def predict_paragraphs(self, *a, **k):
        return []


class TokStub:
    def __call__(self, text, return_tensors="pt", truncation=False, **kw):
        class E:
            pass

        e = E()
        e.input_ids = torch.randint(1, 90, (1, 12))
        return e


try:
    p = Probe({"id": "probe"}, r"d:\Project\AIGC\app")
    lp = p.avg_logprob("hello world test", m, TokStub(), "cpu", chunk=4)
    print("   OK  avg_logprob = %.6f（真跑通，chunk=4 分块）" % lp)
    lp2 = p.avg_logprob("hello world test", m, TokStub(), "cpu", chunk=256)
    print("   OK  avg_logprob = %.6f（chunk=256 单块）" % lp2)
except Exception as e:
    print("   FAIL %s: %s" % (type(e).__name__, str(e)[:200]))
print()

print("G) 用极小本地模型真跑 Binoculars 打分链路")
try:
    from core.engines.binoculars_engine import BinocularsEngine

    class BinoProbe(BinocularsEngine):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)

        def _get(self, repo, kind, device=None, **kw):
            if kind == "tokenizer":
                return TokStub()
            return m

    bp = BinoProbe({"id": "probe_bino", "impl": "binoculars"}, r"d:\Project\AIGC\app")
    probs = bp.predict_paragraphs(["这是一段测试文本，用于验证公式。"], "cpu")
    print("   OK  Binoculars predict_paragraphs -> %r" % probs)
    print("       （随机权重模型，概率无意义，只看能否跑通）")
except Exception as e:
    import traceback

    print("   FAIL %s: %s" % (type(e).__name__, str(e)[:200]))
    traceback.print_exc(limit=2)
