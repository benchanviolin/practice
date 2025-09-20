#!/usr/bin/env python3
"""
Aggregate JSON practice logs from subdirectories only, grouped by top-level folder,
restricted to files within the last N months based on path date: [domain]/YYYY/MM/DD.json
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from datetime import datetime, date
from calendar import monthrange
from typing import Dict, List

DEFAULT_EXCLUDES = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"}

def is_json(path: Path) -> bool:
    return path.suffix.lower() == ".json"

def months_ago(d: date, months: int) -> date:
    """Return the calendar date `months` months before `d` (clamped to month length)."""
    y = d.year
    m = d.month - months
    while m <= 0:
        m += 12
        y -= 1
    _, max_day = monthrange(y, m)
    return date(y, m, min(d.day, max_day))

def parse_path_date(repo_path: Path, fpath: Path):
    """
    Expect relative path format: [domain]/YYYY/MM/DD.json
    Returns (domain, file_date) or (None, None) if not matching/invalid.
    """
    try:
        rel = fpath.relative_to(repo_path)
    except ValueError:
        return None, None

    parts = rel.parts
    if len(parts) != 4 or not is_json(fpath):
        return None, None

    domain, y, m, dd_json = parts
    if not (y.isdigit() and m.isdigit()):
        return None, None

    try:
        dd = Path(dd_json).stem
        if not dd.isdigit():
            return None, None
        file_date = date(int(y), int(m), int(dd))
    except Exception:
        return None, None

    return domain, file_date

def aggregate_logs(
    repo_path: Path,
    output_file: Path,
    excludes: set[str],
    follow_symlinks: bool,
    months: int,
) -> Path:
    repo_path = repo_path.resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")

    today = date.today()
    cutoff = months_ago(today, months)

    groups: Dict[str, List[dict]] = {}
    skipped_files: List[str] = []
    counts = {"total_files_found": 0, "total_parsed": 0, "total_skipped": 0, "total_within_window": 0}
    group_meta: Dict[str, Dict[str, int]] = {}

    print(f"Scanning subdirectories of: {repo_path}")
    print(f"Time window: files dated from {cutoff.isoformat()} to {today.isoformat()} (inclusive)")

    for dirpath, dirnames, filenames in os.walk(repo_path, followlinks=follow_symlinks):
        # prune excluded directories
        dirnames[:] = [d for d in dirnames if d not in excludes]

        dirpath_p = Path(dirpath)
        # Skip root-level files; only process subdirs
        if dirpath_p.resolve() == repo_path:
            continue

        for fname in filenames:
            fpath = dirpath_p / fname
            if not is_json(fpath):
                continue

            counts["total_files_found"] += 1

            domain, fdate = parse_path_date(repo_path, fpath)
            if domain is None or fdate is None:
                # Not matching the enforced structure; skip but record
                msg = f"{fpath}: path does not match [domain]/YYYY/MM/DD.json"
                skipped_files.append(msg)
                counts["total_skipped"] += 1
                continue

            # Filter by date window
            if not (cutoff <= fdate <= today):
                continue  # out of window; silently excluded from totals except found
            counts["total_within_window"] += 1

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict):
                    item = data
                elif isinstance(data, list):
                    item = {"logs": data}
                else:
                    raise ValueError(f"Unsupported JSON root type: {type(data).__name__}")

                item["_source_file"] = str(fpath.relative_to(repo_path))
                item["_file_modified"] = datetime.fromtimestamp(fpath.stat().st_mtime).isoformat()
                item["_group"] = domain
                item["_log_date"] = fdate.isoformat()

                groups.setdefault(domain, []).append(item)
                gm = group_meta.setdefault(domain, {"found_in_window": 0, "parsed": 0, "skipped": 0})
                gm["found_in_window"] += 1
                gm["parsed"] += 1
                counts["total_parsed"] += 1

            except json.JSONDecodeError as e:
                msg = f"{fpath}: JSON decode error: {e}"
                skipped_files.append(msg)
                counts["total_skipped"] += 1
                gm = group_meta.setdefault(domain, {"found_in_window": 0, "parsed": 0, "skipped": 0})
                gm["found_in_window"] += 1
                gm["skipped"] += 1
            except Exception as e:
                msg = f"{fpath}: {e}"
                skipped_files.append(msg)
                counts["total_skipped"] += 1
                gm = group_meta.setdefault(domain, {"found_in_window": 0, "parsed": 0, "skipped": 0})
                gm["found_in_window"] += 1
                gm["skipped"] += 1

    aggregated = {
        "metadata": {
            "aggregated_at": datetime.now().isoformat(),
            "source_directory": str(repo_path),
            "excludes": sorted(excludes),
            "window_months": months,
            "window_start": cutoff.isoformat(),
            "window_end": today.isoformat(),
            **counts,
            "groups": {
                g: {
                    "found_in_window": group_meta.get(g, {}).get("found_in_window", 0),
                    "parsed": group_meta.get(g, {}).get("parsed", 0),
                    "skipped": group_meta.get(g, {}).get("skipped", 0),
                }
                for g in sorted(groups.keys() | group_meta.keys())
            },
            "parsing_errors": skipped_files if skipped_files else [],
        },
        "groups": groups,  # { "<domain>": [ { ...item... }, ... ] }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print("\nAggregation complete")
    print(f"✅ Parsed: {counts['total_parsed']}  |  ⚠️ Skipped: {counts['total_skipped']}  |  "
          f"📄 Out: {output_file}  ({size_mb:.2f} MB)")
    if group_meta:
        print("\nPer-group (domain) summary:")
        for g in sorted(group_meta):
            gm = group_meta[g]
            print(f" - {g}: in-window {gm['found_in_window']}, parsed {gm['parsed']}, skipped {gm['skipped']}")
    if skipped_files:
        print("\nFirst few errors:")
        for e in skipped_files[:5]:
            print(f"   - {e}")

    return output_file

def create_ai_prompt_file(aggregated_file: Path, prompt_file: Path = Path("ai_analysis_prompt.txt")) -> Path:
    prompt = """Please analyze these practice logs and provide:

1) SUMMARY: key statistics and overview
2) PATTERNS: trends over time; success/failure patterns; frequency/consistency; skill progressions; correlations
3) INSIGHTS & RECOMMENDATIONS: what's working; improvement areas; suggested focus; anomalies
4) ACTIONABLE TAKEAWAYS: concrete next steps

Aggregated data follows:
"""
    with open(aggregated_file, "r", encoding="utf-8") as f:
        json_content = f.read()

    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)
        f.write(json_content)

    size_mb = prompt_file.stat().st_size / (1024 * 1024)
    print(f"🤖 AI analysis prompt created: {prompt_file}  ({size_mb:.2f} MB)")
    if size_mb > 10:
        print("⚠️ Large file; may exceed context limits. Consider filtering by date or domain.")
    return prompt_file

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Aggregate JSON logs from subdirectories, grouped by domain, limited to last N months.")
    p.add_argument("repo", nargs="?", default=".", help="Path to repo root (default: .)")
    p.add_argument("-o", "--output", default="aggregated_logs.json", help="Output JSON file path")
    p.add_argument("-x", "--exclude", action="append", default=[], help="Directory name to exclude (may repeat)")
    p.add_argument("--follow-symlinks", action="store_true", help="Follow directory symlinks")
    p.add_argument("--no-prompt", action="store_true", help="Do not generate ai_analysis_prompt.txt")
    p.add_argument("--months", type=int, default=3, help="How many months back from today to include (default: 3)")
    return p.parse_args()

def main() -> None:
    args = parse_args()
    repo = Path(args.repo)
    output = Path(args.output)
    excludes = DEFAULT_EXCLUDES | set(args.exclude)

    out = aggregate_logs(
        repo_path=repo,
        output_file=output,
        excludes=excludes,
        follow_symlinks=args.follow_symlinks,
        months=max(1, args.months),
    )
    if not args.no_prompt:
        create_ai_prompt_file(out)

    print("\nNext:")
    print("  - Validate metadata.window_* and metadata.groups")
    print("  - Adjust --months or domain-level filtering if needed")

if __name__ == "__main__":
    main()
