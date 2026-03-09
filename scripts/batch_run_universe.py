from __future__ import annotations

import argparse
import json
import time
import traceback
from copy import deepcopy
from pathlib import Path

import yaml

from data.smart_loader import get_available_tickers
from thothmind.run import run_experiment
from thothmind.registry import compute_cfg_hash


def load_done_keys(state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()
    done = set()
    for line in state_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("status") == "ok" and obj.get("key"):
                done.add(obj["key"])
        except Exception:
            continue
    return done


def append_state(state_path: Path, obj: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def newest_run_dir(output_dir: Path, before: set[str]) -> Path | None:
    after_dirs = {p.name for p in output_dir.glob("*") if p.is_dir()}
    new = list(after_dirs - before)
    if not new:
        return None
    if len(new) == 1:
        return output_dir / new[0]
    # fallback: choose the most recently modified
    cand = [output_dir / n for n in new]
    cand.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cand[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs-glob", default="configs/exp_m[1-7]*.yaml",
                    help="Glob pattern for configs (PowerShell: use quotes).")
    ap.add_argument("--data-root", default="data",
                    help="Path to data folder with Stocks/ETFs.")
    ap.add_argument("--output-dir", default="reports/runs",
                    help="Where thothmind stores run folders.")
    ap.add_argument("--state", default="reports/batch_state.jsonl",
                    help="JSONL file for resume/skip.")
    ap.add_argument("--max-tickers", type=int, default=0,
                    help="0 = all tickers. For testing set e.g. 5.")
    ap.add_argument("--resume", action="store_true",
                    help="Skip combos already marked ok in state.")
    ap.add_argument("--skip-suite", action="store_true",
                    help="Skip configs that have 'suite' key (m8). Recommended for universe runs.")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    configs = sorted((repo_root).glob(args.configs_glob))
    if not configs:
        print(f"[ERR] No configs matched: {args.configs_glob}")
        return 2

    data_root = (repo_root / args.data_root).resolve()
    tickers = get_available_tickers(data_root)
    tickers.sort()

    if args.max_tickers and args.max_tickers > 0:
        tickers = tickers[:args.max_tickers]

    output_dir = (repo_root / args.output_dir).resolve()
    state_path = (repo_root / args.state).resolve()
    done_keys = load_done_keys(state_path) if args.resume else set()

    print(f"[INFO] configs: {len(configs)} | tickers: {len(tickers)} | output: {output_dir}")
    print(f"[INFO] resume={args.resume} | skip_suite={args.skip_suite} | state={state_path}")

    tmp_cfg_path = repo_root / "configs" / "_tmp_active.yaml"

    for cfg_path in configs:
        base_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

        if args.skip_suite and isinstance(base_cfg, dict) and "suite" in base_cfg:
            print(f"[SKIP] {cfg_path.name} (suite-config)")
            continue

        for t in tickers:
            cfg = deepcopy(base_cfg)
            cfg.setdefault("data", {})
            cfg["data"]["ticker"] = t

            cfg_hash = compute_cfg_hash(cfg)
            key = f"{cfg_path.name}::{t}::{cfg_hash}"

            if args.resume and key in done_keys:
                continue

            tmp_cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")

            before = {p.name for p in output_dir.glob("*") if p.is_dir()}
            ts0 = time.time()
            try:
                run_experiment(str(tmp_cfg_path))
                run_dir = newest_run_dir(output_dir, before)
                append_state(state_path, {
                    "status": "ok",
                    "key": key,
                    "config": cfg_path.name,
                    "ticker": t,
                    "cfg_hash": cfg_hash,
                    "run_dir": str(run_dir) if run_dir else None,
                    "seconds": round(time.time() - ts0, 3),
                })
                done_keys.add(key)
                print(f"[OK] {cfg_path.name} | {t} | {round(time.time()-ts0,1)}s")
            except Exception as e:
                append_state(state_path, {
                    "status": "err",
                    "key": key,
                    "config": cfg_path.name,
                    "ticker": t,
                    "cfg_hash": cfg_hash,
                    "error": repr(e),
                    "traceback": traceback.format_exc(),
                    "seconds": round(time.time() - ts0, 3),
                })
                print(f"[ERR] {cfg_path.name} | {t} | {e}")

    print("[DONE]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())