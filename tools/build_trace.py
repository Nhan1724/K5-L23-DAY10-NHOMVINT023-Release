#!/usr/bin/env python3
"""Phase 5 automation: build trace.json from delivery ticket, changelog, jobs.csv, and YOLO labels.

Usage:
  python3 tools/build_trace.py --delivery runs/r23007/delivery --out runs/r23007/trace.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def parse_version(ver: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", ver)
    return tuple(int(n) for n in nums) if nums else (0,)


def load_classes(path: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        idx_str, name = line.split(" ", 1)
        mapping[name.strip()] = int(idx_str)
    return mapping


def parse_changelog(changelog_text: str, known_classes: set[str]) -> tuple[str, set[str], str]:
    """Return (latest_version, old_versions, rule_class) from guideline/changelog.md."""
    sections = re.split(r"(?m)^##\s+", changelog_text)
    parsed_sections: list[tuple[str, str]] = []
    for sec in sections[1:]:
        lines = sec.splitlines()
        if not lines:
            continue
        ver_match = re.search(r"v\d+(?:\.\d+)*", lines[0])
        if ver_match:
            parsed_sections.append((ver_match.group(0), "\n".join(lines[1:])))

    if not parsed_sections:
        raise SystemExit("Không tìm thấy heading phiên bản (ví dụ ## v1.3) trong changelog.md")

    parsed_sections.sort(key=lambda item: parse_version(item[0]), reverse=True)
    latest_ver, latest_body = parsed_sections[0]
    old_vers = {ver for ver, _ in parsed_sections[1:]}

    rule_class = None
    for token in re.findall(r"`([^`]+)`", latest_body):
        if token.strip() in known_classes:
            rule_class = token.strip()
            break

    if rule_class is None:
        m = re.search(r"(?i)lớp\s+['\"`]?([a-zA-Z0-9_ ]+?)['\"`]?\s*:", latest_body)
        if m and m.group(1).strip() in known_classes:
            rule_class = m.group(1).strip()

    if rule_class is None:
        raise SystemExit(f"Không xác định được lớp đổi quy tắc trong changelog.md (section {latest_ver})")

    return latest_ver, old_vers, rule_class


def parse_ticket_scenes(ticket_text: str) -> list[str]:
    seen: set[str] = set()
    scenes: list[str] = []
    for sc in re.findall(r"scene_\d+", ticket_text):
        if sc not in seen:
            seen.add(sc)
            scenes.append(sc)
    if not scenes:
        raise SystemExit("Không tìm thấy scene_xxx nào trong incoming/ticket.md")
    return scenes


def build_trace(delivery: Path) -> tuple[dict, dict]:
    class_to_id = load_classes(delivery / "classes.txt")
    changelog_text = (delivery / "guideline" / "changelog.md").read_text(encoding="utf-8")
    ticket_text = (delivery / "incoming" / "ticket.md").read_text(encoding="utf-8")

    latest_ver, old_vers, rule_class = parse_changelog(changelog_text, set(class_to_id))
    rule_class_id = class_to_id[rule_class]
    reported_scenes = set(parse_ticket_scenes(ticket_text))

    with (delivery / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {row["job_id"].strip(): row for row in csv.DictReader(f)}

    all_job_guidelines = {j["guideline"].strip() for j in jobs.values()}
    # Any job guideline strictly older than latest_ver is treated as old guideline.
    target_old_guidelines = {g for g in all_job_guidelines if parse_version(g) < parse_version(latest_ver)}
    if not target_old_guidelines:
        target_old_guidelines = old_vers & all_job_guidelines

    manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta_items = json.loads((delivery / "metadata.json").read_text(encoding="utf-8"))["items"]

    tier_a: list[str] = []
    tier_b: list[str] = []
    affected_jobs: set[str] = set()

    for item in meta_items:
        img = item["image"]
        job_id = item["job_id"]
        job_guideline = jobs[job_id]["guideline"].strip()
        # Critical rule: ALWAYS use job guideline from jobs.csv, never metadata guideline_version.
        if job_guideline not in target_old_guidelines:
            continue

        label_rel = manifest[img]["label"] if img in manifest else f"labels/{img}.txt"
        label_path = delivery / label_rel
        if not label_path.is_file():
            continue

        has_rule_class = False
        for line in label_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if not parts:
                continue
            try:
                cid = int(float(parts[0]))
            except ValueError:
                continue
            if cid == rule_class_id:
                has_rule_class = True
                break

        if not has_rule_class:
            continue

        affected_jobs.add(job_id)
        if item["scene_id"] in reported_scenes:
            tier_a.append(img)
        else:
            tier_b.append(img)

    tier_a.sort()
    tier_b.sort()
    notify = sorted(
        {jobs[jid]["annotator"].strip() for jid in affected_jobs}
        | {jobs[jid]["reviewer"].strip() for jid in affected_jobs}
    )

    trace = {
        "tier_a": tier_a,
        "tier_b": tier_b,
        "notify": notify,
    }
    meta_summary = {
        "rule_class": rule_class,
        "rule_class_id": rule_class_id,
        "latest_guideline": latest_ver,
        "old_guidelines": sorted(target_old_guidelines),
        "reported_scenes": sorted(reported_scenes),
        "affected_jobs": sorted(affected_jobs),
    }
    return trace, meta_summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Tạo trace.json tự động theo job guideline và ticket")
    ap.add_argument("--delivery", required=True, help="Thư mục delivery/ (ví dụ runs/r23007/delivery)")
    ap.add_argument("--out", required=True, help="Đường dẫn file trace.json đầu ra")
    args = ap.parse_args()

    delivery = Path(args.delivery)
    if not delivery.is_dir():
        raise SystemExit(f"Không thấy thư mục delivery: {delivery}")

    trace, info = build_trace(delivery)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Trace xong -> {out_path}\n"
        f"  Lớp đổi quy tắc : {info['rule_class']} (class_id={info['rule_class_id']})\n"
        f"  Guideline cũ    : {info['old_guidelines']} (mới: {info['latest_guideline']})\n"
        f"  Scene báo lỗi   : {info['reported_scenes']}\n"
        f"  Job bị ảnh hưởng: {info['affected_jobs']}\n"
        f"  tier_a={len(trace['tier_a'])}, tier_b={len(trace['tier_b'])}, notify={trace['notify']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
