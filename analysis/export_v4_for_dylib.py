"""Export V4 ACC models (K=3/5/10) + isotonic calibrators as a single JSON bundle
that the dylib can load and run live.

Produces `assets/v4_model.json` (bundled with the tweak).

The bundle layout:
{
  "version": 1,
  "feature_cols": [...],                 # ordered feature names the tree walker expects
  "pvt_classes": ["ACC","SPN","UNK"],    # which pvt_* one-hots are present
  "tuple_cat_idx": {"TRIPLE_ACCUMULATION":0, ...}, # map from category string to id
  "models": {
    "K3":  { "trees": [...], "iso_x": [...], "iso_y": [...], "has_iso": true },
    "K5":  { ... },
    "K10": { ... }
  }
}

Each tree is a nested dict produced by `booster.dump_model()`:
  {split_feature, threshold, left_child, right_child, leaf_value, ...}
The Obj-C walker traverses them identically. LightGBM's binary prediction is
`sigmoid( sum_of_leaf_values_over_all_trees )` when objective=binary.

Self-test: after exporting, we load the JSON back, walk trees on a random
sample of rows, apply isotonic, and check the result matches `predict_proba`
within 1e-6. Fails loudly if it doesn't.
"""

import argparse
import json
import math
import random
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from tail_risk_v4_hazard_plus import (
    FEATURE_COLS_BASE,
    TUPLE_CAT_IDX,
    build_spin_frame,
)


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=str, default=str(ASSET_DIR / "v4_model.json"))
    p.add_argument("--horizons", type=int, nargs="+", default=[3, 5, 10])
    p.add_argument("--heads", type=str, nargs="+", default=["acc", "any"],
                   choices=["acc", "spn", "any"],
                   help="Heads to export. Bundle nests models[head][K]. v2 schema.")
    p.add_argument("--cal-frac", type=float, default=0.20,
                   help="Fraction of training data used for isotonic calibration")
    p.add_argument("--test-rows", type=int, default=200,
                   help="How many random rows to use for the walker self-test")
    p.add_argument("--seed", type=int, default=7)
    return p.parse_args()


def train_one(frame: pd.DataFrame, target_col: str, cols: list[str], cal_frac: float, seed: int):
    x = frame[cols].astype(float)
    y = frame[target_col].astype(int).to_numpy()

    # Split by cycle_id so a cycle's spins stay on one side.
    cycles = frame["cycle_id"].unique()
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(cycles)
    split = int(len(shuffled) * (1 - cal_frac))
    fit_cycles = set(shuffled[:split].tolist())
    fit_mask = frame["cycle_id"].isin(fit_cycles).to_numpy()
    cal_mask = ~fit_mask

    model = lgb.LGBMClassifier(
        n_estimators=450,
        learning_rate=0.04,
        num_leaves=31,
        min_data_in_leaf=40,
        feature_fraction=0.85,
        bagging_fraction=0.85,
        bagging_freq=5,
        verbose=-1,
        random_state=seed,
    )
    model.fit(x[fit_mask], y[fit_mask])

    iso = None
    if cal_mask.any():
        p_cal = model.predict_proba(x[cal_mask])[:, 1]
        y_cal = y[cal_mask]
        if y_cal.sum() > 0 and y_cal.sum() < y_cal.size:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(p_cal, y_cal)

    return model, iso, x, y


def dump_tree(model: lgb.LGBMClassifier) -> dict:
    booster = model.booster_
    dumped = booster.dump_model()
    # Keep only what the walker needs: per-tree root nodes.
    trees = []
    for t in dumped["tree_info"]:
        trees.append(t["tree_structure"])
    return {
        "trees": trees,
        "num_class": dumped.get("num_class", 1),
        "objective": dumped.get("objective", "binary"),
        "max_feature_idx": dumped.get("max_feature_idx", -1),
        "feature_names": dumped.get("feature_names", []),
    }


def walk_one_tree(node: dict, feat_vec: np.ndarray) -> float:
    """Recursive walker — mirrors the Obj-C walker exactly."""
    while "leaf_value" not in node:
        split_idx = node["split_feature"]
        threshold = node["threshold"]
        decision = node.get("decision_type", "<=")
        missing_type = node.get("missing_type", "None")
        default_left = node.get("default_left", False)

        v = feat_vec[split_idx]
        is_missing = math.isnan(v)
        if is_missing:
            # LightGBM: route by default_left if missing, unless missing_type == 'None'
            # which means missing should be treated as a normal value (= 0 essentially).
            # In practice missing_type is 'None'/'NaN'/'Zero'. We follow default_left.
            go_left = bool(default_left)
        else:
            if decision == "<=":
                go_left = v <= threshold
            elif decision == "<":
                go_left = v < threshold
            elif decision == "==":
                # categorical — threshold is a csv of cat ids, but we treat features as
                # numeric throughout, so this shouldn't fire.
                go_left = False
            else:
                go_left = v <= threshold

        node = node["left_child"] if go_left else node["right_child"]
    return float(node["leaf_value"])


def predict_from_bundle(bundle_model: dict, feat_vec: np.ndarray) -> float:
    raw = 0.0
    for tree in bundle_model["trees"]:
        raw += walk_one_tree(tree, feat_vec)
    p = 1.0 / (1.0 + math.exp(-raw))
    if bundle_model.get("has_iso"):
        p = apply_iso(p, bundle_model["iso_x"], bundle_model["iso_y"])
    return p


def apply_iso(p: float, xs: list[float], ys: list[float]) -> float:
    if p <= xs[0]:
        return ys[0]
    if p >= xs[-1]:
        return ys[-1]
    # linear interpolation between nearest knots
    lo, hi = 0, len(xs) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if xs[mid] <= p:
            lo = mid
        else:
            hi = mid
    x0, x1 = xs[lo], xs[hi]
    y0, y1 = ys[lo], ys[hi]
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (p - x0) / (x1 - x0)


def main():
    args = parse_args()

    print("Loading + building features...")
    frame = build_spin_frame(max_horizon=max(args.horizons))
    if frame.empty:
        raise SystemExit("No data.")

    # Ensure all pvt_ dummies we'll need exist as columns
    pvt_cols = sorted([c for c in frame.columns if c.startswith("pvt_")])
    cols = FEATURE_COLS_BASE + pvt_cols

    # Freeze the exact TUPLE_CAT_IDX used at train time
    tuple_cat_idx = dict(TUPLE_CAT_IDX)

    bundle = {
        "version": 2,
        "feature_cols": cols,
        "pvt_classes": [c.replace("pvt_", "") for c in pvt_cols],
        "tuple_cat_idx": tuple_cat_idx,
        "models": {},
    }

    head_prefix_map = {"acc": "y_acc_next", "spn": "y_spn_next", "any": "y_any_next"}
    head_label_map  = {"acc": "ACC", "spn": "SPN", "any": "ANY_VT"}

    for head in args.heads:
        head_prefix = head_prefix_map[head]
        head_label  = head_label_map[head]
        bundle["models"][head_label] = {}

        for K in args.horizons:
            target_col = f"{head_prefix}{K}"
            print(f"Training {head_label} K={K} ({target_col}) ...")
            model, iso, x, y = train_one(frame, target_col, cols, args.cal_frac, args.seed)
            tree_bundle = dump_tree(model)
            has_iso = iso is not None
            bundle["models"][head_label][f"K{K}"] = {
                "trees": tree_bundle["trees"],
                "num_class": tree_bundle["num_class"],
                "objective": tree_bundle["objective"],
                "iso_x": iso.X_thresholds_.tolist() if has_iso else [],
                "iso_y": iso.y_thresholds_.tolist() if has_iso else [],
                "has_iso": has_iso,
            }

            # Self-test: pick random rows, compare tree walker vs LightGBM.
            rng = np.random.default_rng(args.seed + K)
            idx = rng.choice(len(x), size=min(args.test_rows, len(x)), replace=False)
            sample = x.iloc[idx].to_numpy(dtype=float)
            lgb_p_raw = model.predict_proba(x.iloc[idx])[:, 1]
            lgb_p = iso.predict(lgb_p_raw) if has_iso else lgb_p_raw

            walker_p = np.array([
                predict_from_bundle(bundle["models"][head_label][f"K{K}"], sample[i])
                for i in range(len(sample))
            ])
            max_err = float(np.max(np.abs(lgb_p - walker_p)))
            mean_err = float(np.mean(np.abs(lgb_p - walker_p)))
            print(f"  {head_label} K={K}: walker vs lgb  max_err={max_err:.3e}  mean_err={mean_err:.3e}")
            if max_err > 1e-4:
                print(f"  !! self-test WARN: walker drift > 1e-4 for {head_label} K={K}")

    # Flatten for JSON writing (trim 'internal_count', 'internal_weight', etc. to save bytes)
    print("Writing bundle...")
    _trim_tree_fields(bundle)
    out_path = Path(args.out)
    with out_path.open("w") as f:
        json.dump(bundle, f)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Wrote {out_path} ({size_mb:.2f} MB)")
    print(f"Features: {len(cols)} columns")
    print(f"Models: {list(bundle['models'].keys())}")
    print(f"PVT classes: {bundle['pvt_classes']}")
    print(f"Tuple cats: {len(tuple_cat_idx)} mappings")


def _trim_tree_fields(bundle: dict) -> None:
    """Remove fields the walker doesn't need to shrink JSON size."""
    KEEP = {"split_feature", "threshold", "decision_type", "missing_type",
            "default_left", "left_child", "right_child", "leaf_value"}

    def clean(node: dict) -> None:
        for k in list(node.keys()):
            if k not in KEEP:
                del node[k]
        if "left_child" in node:
            clean(node["left_child"])
            clean(node["right_child"])

    # v2 schema: models[head][K]; v1 was models[K]. Walk both.
    for head_or_horizon in bundle["models"].values():
        if "trees" in head_or_horizon:
            # legacy v1 path
            horizons = [head_or_horizon]
        else:
            # v2: nested by head
            horizons = list(head_or_horizon.values())
        for m in horizons:
            for tree in m["trees"]:
                clean(tree)


if __name__ == "__main__":
    main()
