#!/usr/bin/env python3
"""Quick perf benchmark for localisation parsing."""

from __future__ import annotations

import argparse
import cProfile
import io
from pathlib import Path
import pstats
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


def _run_once(
    files: list[Path],
    *,
    label: str,
    show_progress: bool,
) -> tuple[float, int, int, int]:
    start = time.perf_counter()
    total_entries = 0
    total_diagnostics = 0
    iterator = (
        tqdm(files, desc=label, unit="file")
        if show_progress
        else files
    )
    for path in iterator:
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
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable tqdm progress bars (useful for pure timing)",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Run cProfile and print top hotspots",
    )
    parser.add_argument(
        "--profile-top",
        type=int,
        default=30,
        help="Number of cProfile rows to print (default: 30)",
    )
    parser.add_argument(
        "--profile-sort",
        type=str,
        default="tottime",
        help="cProfile sort key (default: tottime, common: cumulative)",
    )
    parser.add_argument(
        "--limit-files",
        type=int,
        default=0,
        help="Optional file limit for quick profiling/smoke tests (0 = all files)",
    )
    args = parser.parse_args()

    loc_root: Path = args.loc_root
    if not loc_root.exists() or not loc_root.is_dir():
        raise SystemExit(f"Invalid --loc-root: {loc_root}")

    files = _collect_loc_files(loc_root)
    if not files:
        raise SystemExit(f"No .yml/.yaml files found under {loc_root}")
    if args.limit_files > 0:
        files = files[: args.limit_files]

    show_progress = not args.no_progress

    def _benchmark() -> tuple[list[float], int, int, int]:
        for warmup_idx in range(max(args.warmups, 0)):
            _run_once(
                files,
                label=f"warmup {warmup_idx + 1}/{max(args.warmups, 0)}",
                show_progress=show_progress,
            )

        timings: list[float] = []
        files_count = 0
        entries_count = 0
        diagnostics_count = 0
        for run_idx in range(max(args.runs, 1)):
            duration, files_count, entries_count, diagnostics_count = _run_once(
                files,
                label=f"run {run_idx + 1}/{max(args.runs, 1)}",
                show_progress=show_progress,
            )
            timings.append(duration)
        return timings, files_count, entries_count, diagnostics_count

    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
        timings, files_count, entries_count, diagnostics_count = _benchmark()
        profiler.disable()
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats(args.profile_sort).print_stats(max(args.profile_top, 1))
        print("\n[cProfile top functions]")
        print(stream.getvalue())
    else:
        timings, files_count, entries_count, diagnostics_count = _benchmark()

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
