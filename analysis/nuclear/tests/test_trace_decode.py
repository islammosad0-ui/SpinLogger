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
