import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import save_json


def compute_cfg_hash(cfg: dict) -> str:
    cfg_bytes = json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(cfg_bytes).hexdigest()[:12]


def make_run_id(cfg: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    h = compute_cfg_hash(cfg)[:10]
    return f"{ts}_{h}"


def init_run_dir(run_id: str, output_root: str = "reports/runs") -> Path:
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_run_artifacts(run_dir: Path, cfg: dict) -> None:
    manifest = {
        "run_id": run_dir.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "cfg_hash": compute_cfg_hash(cfg),
    }

    save_json(cfg, run_dir / "config.json")
    save_json(manifest, run_dir / "manifest.json")
