#!/usr/bin/env python3
"""
Aggregate JSON practice logs from subdirectories only, grouped by top-level folder.
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

DEFAULT_EXCLUDES = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"}

def is_json(path: Path) -> bool:
    return path.suffix.lower() == ".json"

def aggregate_logs(
    repo_path: Path,
    output_file: Path,
    excludes: set[str],
    follow_symlinks: bool = False
) -> Path:
    repo_path = repo_path.resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")

    groups: Dict[str, List[dict]] = {}
    skipped_files: List[str] = []
    counts = {
        "total_files_found": 0,
        "total_parsed": 0,
        "total_skipped": 0,
    }
    group_meta: Dict[str, Dict[str, int]] = {}

    print(f"Scanning subdirectories of: {repo_path}")
    for dirpath, dirnames, filenames in os.walk(repo_path, followlinks=follow_symlinks):
        # prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if d not in excludes]

        dirpath_p = Path(dirpath)

        # Skip JSON files in the root of the repo; only process subdirs
        if dirpath_p.resolve() == repo_path:
            continue

        rel_dir = dirpath_p.relative_to(repo_path)
        if not rel_dir.parts:
            # extra safety; should not happen due to the continue above
            continue

        top_level_group = rel_dir.parts[0]

        for fname in filenames:
            fpath = dirpath_p / fname
            if not is_json(fpath):
                continue

            counts["total_files_found"] += 1

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Normalize to dict with metadata
                if isinstance(data, dict):
                    item = data
                elif isinstance(data, list):
                    item = {"logs": data}
                else:
                    # Unhandled JSON root type
                    raise ValueError(f"Unsupported JSON root type: {type(data).__name__}")

                item["_source_file"] = str(fpath.relative_to(repo_path))
                item["_file_modified"] = datetime.fromtimestamp(fpath.stat().st_mtime).isoformat()
                item["_group"] = top_level_group

                groups.setdefault(top_level_group, []).append(item)
                group_meta.setdefault(top_level_group, {"found": 0, "parsed": 0, "skipped": 0})
                group_meta[top_level_group]["found"] += 1
                group_meta[top_level_group]["parsed"] += 1
                counts["total_parsed"] += 1

            except json.JSONDecodeError as e:
                msg = f"{fpath}: JSON decode error: {e}"
                skipped_files.append(msg)
                counts["total_skipped"] += 1
                group_meta.setdefault(top_level_group, {"found": 0, "parsed": 0, "skipped": 0})
                group_meta[top_level_group]["found"] += 1
                group_meta[top_level_group]["skipped"] += 1
            except Exception as e:
                msg = f"{fpath}: {e}"
                skipped_files.append(msg)
                counts["total_skipped"] += 1
                group_meta.setdefault(top_level_group, {"found": 0, "parsed": 0, "skipped": 0})
                group_meta[top_level_group]["found"] += 1
                group_meta[top_level_group]["skipped"] += 1

    aggregated = {
        "metadata": {
            "aggregated_at": datetime.now().isoformat(),
            "source_directory": str(repo_path),
            "excludes": sorted(excludes),
            **counts,
            "groups": {
                g: {
                    "files_found": group_meta.get(g, {}).get("found", 0),
                    "parsed": group_meta.get(g, {}).get("parsed", 0),
                    "skipped": group_meta.get(g, {}).get("skipped", 0),
                }
                for g in sorted(groups.keys() | group_meta.keys())
            },
            "parsing_errors": skipped_files if skipped_files else [],
        },
        "groups": groups,  # { "<top-level-subdir>": [ { ...item... }, ... ] }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print("\nAggregation complete")
    print(f"✅ Parsed: {counts['total_parsed']}  |  ⚠️ Skipped: {counts['total_skipped']}  |  📄 Out: {output_file}  ({size_mb:.2f} MB)")
    if group_meta:
        print("\nPer-group summary:")
        for g in sorted(group_meta):
            gm = group_meta[g]
            print(f" - {g}: found {gm['found']}, parsed {gm['parsed']}, skipped {gm['skipped']}")
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
        print("⚠️ Large file; may exceed context limits. Consider filtering by date or group.")
    return prompt_file

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Aggregate JSON logs from subdirectories, grouped by top-level folder.")
    p.add_argument("repo", nargs="?", default=".", help="Path to repo root (default: .)")
    p.add_argument("-o", "--output", default="aggregated_logs.json", help="Output JSON file path")
    p.add_argument("-x", "--exclude", action="append", default=[], help="Directory name to exclude (may repeat)")
    p.add_argument("--follow-symlinks", action="store_true", help="Follow directory symlinks")
    p.add_argument("--no-prompt", action="store_true", help="Do not generate ai_analysis_prompt.txt")
    return p.parse_args()

def main() -> None:
    args = parse_args()
    repo = Path(args.repo)
    output = Path(args.output)
    excludes = DEFAULT_EXCLUDES | set(args.exclude)

    out = aggregate_logs(repo, output, excludes, follow_symlinks=args.follow_symlinks)
    if not args.no_prompt:
        create_ai_prompt_file(out)

    print("\nNext:")
    print("  - Review group summaries in metadata.groups")
    print("  - Filter or sample if the prompt file is too large")

if __name__ == "__main__":
    main()

