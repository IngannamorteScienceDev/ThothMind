import json
from pathlib import Path
import pandas as pd

runs_dir = Path("reports/runs")
latest = sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)[:10]

print("Latest run dirs:")
for p in latest:
    print("-", p)

print("\nQuick sim checks:")
for p in latest:
    sim_path = p / "sim_oos.csv"
    if not sim_path.exists():
        sim_path = p / "sim.csv"
    if not sim_path.exists():
        continue

    df = pd.read_csv(sim_path)
    cols = [c for c in ["position", "daily_return", "strategy_return", "turnover", "capital"] if c in df.columns]
    print(f"\n{p.name}")
    print("columns:", cols)

    if "strategy_return" in df.columns:
        s = pd.to_numeric(df["strategy_return"], errors="coerce").dropna()
        if not s.empty:
            print("strategy_return min/max:", float(s.min()), float(s.max()))

    if "capital" in df.columns:
        c = pd.to_numeric(df["capital"], errors="coerce").dropna()
        if not c.empty:
            print("final capital:", float(c.iloc[-1]))