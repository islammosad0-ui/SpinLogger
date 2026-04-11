import importlib.util
import sys
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"
MOD_PATH = Path(__file__).parent.parent / "50_il2cpp_trace_decode.py"

# importlib because the filename starts with a digit.
# Must register in sys.modules before exec for @dataclass to resolve types on 3.12+.
spec = importlib.util.spec_from_file_location("trace_decode", MOD_PATH)
trace_decode = importlib.util.module_from_spec(spec)
sys.modules["trace_decode"] = trace_decode
spec.loader.exec_module(trace_decode)


def test_load_jsonl_returns_snapshots():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    assert len(snaps) >= 3
    assert all(hasattr(s, "spin_num") for s in snaps)


def test_segment_groups_by_spin_num():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    assert 64200 in buckets
    assert buckets[64200].settled is not None


def test_payline_sanity_matches_ground_truth():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    import pandas as pd
    hist = pd.read_csv(FIX / "tiny_spin_history.csv")
    result = trace_decode.stage2_payline_sanity(buckets, hist)
    # Fixture is crafted so all 3 spins match
    assert result["match_rate"] == 1.0
    assert result["n_spins_checked"] == 3
    assert result["mismatches"] == []


def test_stage3_classifies_counter_field():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    import pandas as pd
    hist = pd.read_csv(FIX / "tiny_spin_history.csv")
    report = trace_decode.stage3_field_change_map(buckets, hist)
    entry = next(r for r in report if r["field"] == "m_SpinFailedCounterGlobal")
    assert entry["type_guess"] in ("counter_like", "resetting_counter")
    assert entry["unique_count"] >= 2


def test_stage4_decodes_strip_stride_and_offset():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    import pandas as pd
    hist = pd.read_csv(FIX / "tiny_spin_history.csv")
    result = trace_decode.stage4_strip_decoder(buckets, hist, reel=1)
    assert result["stride"] == 8
    assert result["inner_offset"] == 0
    assert result["match_rate"] >= 0.9


def test_stage5_identifies_pity_counter():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    import pandas as pd
    hist = pd.read_csv(FIX / "tiny_spin_history.csv")
    report = trace_decode.stage5_pity_counter_hunt(buckets, hist, fail_threshold=8)
    assert len(report) >= 1
    top = report[0]
    assert top["field"] == "m_SpinFailedCounterGlobal"
    assert top["resets_on_triple"]
    assert top["monotonic_between_triples"]
