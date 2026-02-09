#!/usr/bin/env python3
"""Quick perf benchmark for localisation parsing."""

from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import time

from tqdm import tqdm

from jominipy.localisation import parse_localisation_file
from jominipy.localisation.profile import HOI4_PROFILE

DEFAULT_LOC_ROOT = Path(
    "/Users/harrisonchan/Programming/paradox/jominipy/references/Millennium_Dawn/localisation"
)


def _collect_loc_files(root: Path) -> list[Path]:
    files = sorted([*root.rglob("*.yml"), *root.rglob("*.yaml")])
    return [path for path in files if path.is_file()]


def _run_once(files: list[Path], *, label: str) -> tuple[float, int, int, int]:
    start = time.perf_counter()
    total_entries = 0
    total_diagnostics = 0
    for path in tqdm(files, desc=label, unit="file"):
        parsed = parse_localisation_file(path, profile=HOI4_PROFILE)
        total_entries += len(parsed.entries)
        total_diagnostics += len(parsed.diagnostics)
    duration = time.perf_counter() - start
    return duration, len(files), total_entries, total_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark localisation parsing throughput")
    parser.add_argument(
        "--loc-root",
        type=Path,
        default=DEFAULT_LOC_ROOT,
        help="Path to localisation directory (default: Millennium Dawn loc root)",
    )
    parser.add_argument("--runs", type=int, default=5, help="Measured runs")
    parser.add_argument("--warmups", type=int, default=1, help="Warmup runs")
    args = parser.parse_args()

    loc_root: Path = args.loc_root
    if not loc_root.exists() or not loc_root.is_dir():
        raise SystemExit(f"Invalid --loc-root: {loc_root}")

    files = _collect_loc_files(loc_root)
    if not files:
        raise SystemExit(f"No .yml/.yaml files found under {loc_root}")

    for warmup_idx in range(max(args.warmups, 0)):
        _run_once(files, label=f"warmup {warmup_idx + 1}/{max(args.warmups, 0)}")

    timings: list[float] = []
    files_count = 0
    entries_count = 0
    diagnostics_count = 0
    for run_idx in range(max(args.runs, 1)):
        duration, files_count, entries_count, diagnostics_count = _run_once(
            files,
            label=f"run {run_idx + 1}/{max(args.runs, 1)}",
        )
        timings.append(duration)

    best = min(timings)
    worst = max(timings)
    mean = statistics.mean(timings)
    median = statistics.median(timings)

    print(f"Dataset: {loc_root}")
    print(f"Files: {files_count}")
    print(f"Entries: {entries_count}")
    print(f"Diagnostics: {diagnostics_count}")
    print(f"Runs: {len(timings)} (warmups={max(args.warmups, 0)})")
    print(f"Best:   {best:.4f}s")
    print(f"Median: {median:.4f}s")
    print(f"Mean:   {mean:.4f}s")
    print(f"Worst:  {worst:.4f}s")
    print(f"Files/s (mean):   {files_count / mean:.1f}")
    print(f"Entries/s (mean): {entries_count / mean:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
