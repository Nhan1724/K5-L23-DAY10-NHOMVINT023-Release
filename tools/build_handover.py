#!/usr/bin/env python3
"""Phase 3 & 4 automation: build non-overwriting v2 handover, record lineage, pack zip+sha256, and run check_handover.

Usage:
  python3 tools/build_handover.py --run runs/r23007
  python3 tools/build_handover.py --run runs/r23007 --rules runs/r23007/rules.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import metrics  # noqa: E402

DET_REWORK = {
    "missing_image",
    "invalid_class",
    "bbox_out_of_bounds",
    "duplicate_box",
    "class_swap",
    "bbox_drift",
    "missing_box",
}
PANOPTIC_ONLY = {"invalid_category_id", "thing_overlap", "category_swap", "instance_merge"}
REWORK_ACTIONS = {
    "missing_image": "Bổ sung ảnh gốc bị thiếu và kiểm lại nhãn detection",
    "wrong_hash": "Kiểm tra file ảnh hỏng, tải/chụp lại và gán lại nếu cần",
    "invalid_class": "Sửa class_id ngoài 0-79 và rà soát lại toàn ảnh",
    "bbox_out_of_bounds": "Cắt/chỉnh lại bbox vượt mép về đúng ranh giới vật",
    "duplicate_box": "Xoá box detection bị lặp trùng và kiểm lại đối tượng",
    "class_swap": "Gán lại đúng tên lớp detection cho đối tượng bị nhầm",
    "bbox_drift": "Chỉnh lại toạ độ bbox detection khớp đúng biên vật",
    "missing_box": "Gán bổ sung bbox detection cho vật bị bỏ sót",
}
THRESHOLD = 0.02


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_script(script: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=check)


def format_guideline_summary(jobs: list[dict[str, str]]) -> str:
    by_ver: dict[str, list[str]] = {}
    for row in jobs:
        by_ver.setdefault(row["guideline"].strip(), []).append(row["job_id"].strip())
    parts = []
    for ver in sorted(by_ver):
        jids = sorted(by_ver[ver])
        if len(jids) >= 3:
            parts.append(f"{ver} ({jids[0]}–{jids[-1]})")
        else:
            parts.append(f"{ver} ({', '.join(jids)})")
    return ", ".join(parts)


def verify_h3_preconditions(errors: list[dict], review_path: Path) -> None:
    if not review_path.is_file():
        raise SystemExit(f"Thiếu {review_path}. Cả nhóm cần xem ảnh và tạo review_log.csv trước.")
    with review_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{review_path} đang rỗng.")
    confirmed = {
        (r.get("type", "").strip(), r.get("image", "").strip())
        for r in rows
        if r.get("verdict", "").strip() == "confirmed"
    }
    need = {(e["type"], e["target"]) for e in errors if e["type"] in metrics.SEMANTIC_TYPES}
    missing = need - confirmed
    if missing:
        raise SystemExit(f"H3 FAIL: errors.json có {len(missing)} lỗi gán nhãn chưa confirmed trong review_log.csv: {sorted(missing)[:5]}")
    notes = [(r.get("note") or "").strip() for r in rows]
    short = [r.get("image") for r in rows if len((r.get("note") or "").strip()) < 20]
    if short:
        raise SystemExit(f"H3 FAIL: review_log.csv có ghi chú < 20 ký tự ở các ảnh: {short[:5]}")
    if len(set(notes)) < 0.7 * len(notes):
        raise SystemExit("H3 FAIL: ghi chú trong review_log.csv trùng lặp quá nhiều (cần >= 70% khác nhau).")


def resolve_scene_splits(meta_items: list[dict]) -> dict[str, str]:
    counts: dict[str, Counter[str]] = {}
    for item in meta_items:
        counts.setdefault(item["scene_id"], Counter())[item["split"]] += 1
    resolved: dict[str, str] = {}
    for scene_id, counter in counts.items():
        # Majority split (tie-breaker: deterministic alphabetical order)
        best_split = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        resolved[scene_id] = best_split
    return resolved


def has_lineage_event(lineage_path: Path, event: str, release_id: str, **fields: str) -> bool:
    if not lineage_path.is_file():
        return False
    for line in lineage_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("event") == event and row.get("release_id") == release_id:
            if all(row.get(k) == v for k, v in fields.items()):
                return True
    return False


def build_handover(
    run_dir: Path,
    rules_path: Path | None,
    corrupt_hashes: set[str],
    skip_lineage: bool = False,
    hash_checked_by: str = "",
) -> int:
    delivery = run_dir / "delivery"
    if not delivery.is_dir():
        raise SystemExit(f"Không thấy thư mục delivery: {delivery}")

    review_path = run_dir / "review_log.csv"
    errors_path = run_dir / "errors.json"

    if rules_path and rules_path.is_file():
        if not review_path.is_file():
            raise SystemExit(f"Đã có {rules_path} nhưng thiếu {review_path}. Hãy hoàn thành review ảnh trước khi chạy handover.")
        run_script("merge_review.py", "--rules", str(rules_path), "--review", str(review_path), "--out", str(errors_path))
    elif not errors_path.is_file():
        raise SystemExit(f"Thiếu {errors_path} (hoặc {rules_path}).")

    errors = json.loads(errors_path.read_text(encoding="utf-8"))["errors"]
    verify_h3_preconditions(errors, review_path)

    rid = json.loads((delivery / "release.json").read_text(encoding="utf-8"))["release_id"]
    manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta_items = json.loads((delivery / "metadata.json").read_text(encoding="utf-8"))["items"]
    meta_by_img = {m["image"]: m for m in meta_items}

    with (delivery / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs_list = list(csv.DictReader(f))
    jobs = {row["job_id"].strip(): row for row in jobs_list}

    classes = [
        line.split(" ", 1)[1].strip()
        for line in (delivery / "classes.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # Map image-level errors
    rework_map: dict[str, list[str]] = {}
    wrong_hash_imgs: list[str] = []
    guideline_fix_imgs: list[str] = []
    scene_leak_ids: list[str] = []
    panoptic_only_imgs: list[tuple[str, str]] = []

    for err in errors:
        etype, target = err["type"], err["target"]
        if etype in DET_REWORK and target in manifest:
            rework_map.setdefault(target, []).append(etype)
        elif etype == "wrong_hash" and target in manifest:
            wrong_hash_imgs.append(target)
            if target in corrupt_hashes:
                rework_map.setdefault(target, []).append(etype)
        elif etype == "guideline_mismatch" and target in manifest:
            guideline_fix_imgs.append(target)
        elif etype == "scene_leak":
            scene_leak_ids.append(target)
        elif etype in PANOPTIC_ONLY and target in manifest:
            panoptic_only_imgs.append((target, etype))

    # Trung thực: README.txt chỉ được ghi "đã mở ảnh kiểm" khi có người thật đã kiểm.
    intact_unchecked = sorted(set(wrong_hash_imgs) - corrupt_hashes)
    if intact_unchecked and not hash_checked_by.strip():
        raise SystemExit(
            "Có ảnh wrong_hash chưa được người kiểm: " + ", ".join(intact_unchecked) + "\n"
            "Mở Tab 2 của tools/review_app.py, nhìn từng ảnh, rồi chạy lại với:\n"
            "  --hash-checked-by \"<Tên người đã mở ảnh>\"            (nếu ảnh nguyên vẹn)\n"
            "  --corrupt-hash <tên_ảnh>                               (nếu ảnh hỏng thật -> vào rework)"
        )

    rework_imgs = set(rework_map)
    # Also ensure missing files on disk cannot stay in v2
    for img_name, info in manifest.items():
        if not (delivery / info["image"]).is_file() or not (delivery / info["label"]).is_file():
            if img_name not in rework_imgs:
                rework_map.setdefault(img_name, []).append("missing_image")
                rework_imgs.add(img_name)

    v2_dir = run_dir / "handover" / f"{rid}_v2"
    if v2_dir.exists():
        shutil.rmtree(v2_dir)
    (v2_dir / "images").mkdir(parents=True)
    (v2_dir / "labels").mkdir(parents=True)

    kept_stems = sorted(stem for stem in manifest if stem not in rework_imgs)
    manifest_rows: list[tuple[str, str]] = []
    class_counts: Counter[int] = Counter()

    for stem in kept_stems:
        item = manifest[stem]
        src_img = delivery / item["image"]
        src_lbl = delivery / item["label"]
        dst_img = v2_dir / "images" / f"{stem}.jpg"
        dst_lbl = v2_dir / "labels" / f"{stem}.txt"

        shutil.copyfile(src_img, dst_img)
        shutil.copyfile(src_lbl, dst_lbl)

        manifest_rows.append((f"images/{stem}.jpg", sha256_bytes(dst_img)))
        manifest_rows.append((f"labels/{stem}.txt", sha256_bytes(dst_lbl)))

        for line in dst_lbl.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if parts:
                cid = int(float(parts[0]))
                class_counts[cid] += 1

    # 1. manifest.csv
    manifest_rows.sort(key=lambda r: r[0])
    with (v2_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "sha256"])
        w.writerows(manifest_rows)

    # 2. label_summary.csv (non-zero classes only + TOTAL)
    total_labels = sum(class_counts.values())
    with (v2_dir / "label_summary.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class", "count"])
        for cid in sorted(class_counts):
            cname = classes[cid] if 0 <= cid < len(classes) else str(cid)
            w.writerow([cname, class_counts[cid]])
        w.writerow(["TOTAL", total_labels])

    # 3. rework_queue.csv
    with (v2_dir / "rework_queue.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image", "type", "annotator", "reviewer", "action"])
        for stem in sorted(rework_imgs):
            types = sorted(set(rework_map[stem]))
            etype_str = ";".join(types)
            job = jobs[meta_by_img[stem]["job_id"]]
            action = "; ".join(REWORK_ACTIONS.get(t, "Kiểm tra và gán lại nhãn detection") for t in types)
            w.writerow([stem, etype_str, job["annotator"].strip(), job["reviewer"].strip(), action])

    # 4. truyvet.csv
    scene_splits = resolve_scene_splits(meta_items)
    with (v2_dir / "truyvet.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"])
        for stem in kept_stems:
            m = meta_by_img[stem]
            job = jobs[m["job_id"]]
            w.writerow([
                stem,
                m["scene_id"],
                scene_splits[m["scene_id"]],
                m["job_id"],
                job["annotator"].strip(),
                job["reviewer"].strip(),
                job["guideline"].strip(),
            ])

    # 5. README.txt
    err_targets = {e["target"] for e in errors}
    n_err = len(err_targets)
    n_total = len(manifest)
    rate = n_err / n_total
    over_threshold = rate > THRESHOLD

    v1_decision = (
        f"Hold — tỉ lệ lỗi {n_err}/{n_total} = {rate:.1%} vượt ngưỡng 2% (5/{n_total}); "
        f"không dùng v1 để train, giữ nguyên v1 và tách lô v2 sạch."
        if over_threshold
        else f"Release — tỉ lệ lỗi {n_err}/{n_total} = {rate:.1%} không vượt ngưỡng 2%."
    )
    v2_decision = (
        f"Release — đã tách {len(rework_imgs)} ảnh lỗi nhãn detection/thiếu file sang rework_queue.csv; "
        f"sửa đồng nhất hash, guideline theo job và split theo cảnh; giữ nguyên nhãn gốc cho {len(kept_stems)} ảnh."
    )

    notes_parts = []
    if wrong_hash_imgs:
        intact_wh = [i for i in sorted(set(wrong_hash_imgs)) if i not in corrupt_hashes]
        if intact_wh:
            notes_parts.append(
                f"wrong_hash ({', '.join(intact_wh)}): {hash_checked_by.strip()} đã mở ảnh kiểm, ảnh nguyên vẹn "
                "nên giữ ở v2 và ghi sha256 mới tính lại trong manifest.csv"
            )
        if corrupt_hashes:
            notes_parts.append(f"wrong_hash hỏng ({', '.join(sorted(corrupt_hashes))}): đưa vào rework_queue.csv")
    if guideline_fix_imgs:
        notes_parts.append(f"guideline_mismatch ({', '.join(sorted(set(guideline_fix_imgs)))}): sửa trường guideline trong truyvet.csv khớp jobs.csv")
    if scene_leak_ids:
        detail_sc = [f"{sc}->{scene_splits.get(sc, '?')}" for sc in sorted(set(scene_leak_ids))]
        notes_parts.append(f"scene_leak ({', '.join(detail_sc)}): đưa cả cảnh về một split thống nhất trong truyvet.csv")
    if rework_imgs:
        owners = sorted({f"{jobs[meta_by_img[s]['job_id']]['annotator']}/{jobs[meta_by_img[s]['job_id']]['reviewer']}" for s in rework_imgs})
        notes_parts.append(f"rework ({len(rework_imgs)} ảnh): tách khỏi v2 và giao đúng cặp gán/kiểm ({', '.join(owners)})")
    if panoptic_only_imgs:
        pan_desc = ", ".join(f"{img} ({tp})" for img, tp in sorted(panoptic_only_imgs))
        notes_parts.append(f"lỗi chỉ ở panoptic ({pan_desc}): nhãn detection vẫn đúng nên giữ ở lại v2, đã ghi nhận để báo team panoptic xử lý riêng")

    readme_text = "\n".join([
        f"Release: {rid}_v2",
        f"Parent: {rid}",
        f"Số ảnh: {len(kept_stems)}",
        f"Số nhãn: {total_labels}",
        f"Guideline: {format_guideline_summary(jobs_list)}",
        f"QC v1: {n_err}/{n_total} = {rate:.1%}",
        f"Kết luận v1: {v1_decision}",
        f"Kết luận v2: {v2_decision}",
        f"Ghi chú: {'; '.join(notes_parts)}.",
        "",
    ])
    (v2_dir / "README.txt").write_text(readme_text, encoding="utf-8")

    # 6. Lineage (idempotent append)
    if not skip_lineage:
        lineage_root = run_dir.parent
        lineage_file = lineage_root / "lineage.jsonl"
        if over_threshold and not has_lineage_event(lineage_file, "decision", rid, decision="HOLD"):
            run_script("lineage.py", "--root", str(lineage_root), "record", "--event", "decision", "--release-id", rid, "--decision", "HOLD")
        if not has_lineage_event(lineage_file, "release", f"{rid}_v2", parent=rid):
            run_script("lineage.py", "--root", str(lineage_root), "record", "--event", "release", "--release-id", f"{rid}_v2", "--parent", rid)
        run_script("lineage.py", "--root", str(lineage_root), "impact", "--release-id", rid)

    # 7. Pack zip + sha256
    run_script("pack_release.py", str(v2_dir))

    # 8. Check handover (H1-H17)
    res = run_script("check_handover.py", "--run", str(run_dir), check=False)
    return res.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Tự động hoá Pha 3-4: gộp review, tạo v2, ghi lineage, đóng gói và kiểm check_handover")
    ap.add_argument("--run", required=True, help="Thư mục run (ví dụ runs/r23007)")
    ap.add_argument("--rules", help="Đường dẫn rules.json (mặc định tự tìm <run>/rules.json nếu có)")
    ap.add_argument("--corrupt-hash", default="", help="Danh sách tên ảnh wrong_hash bị hỏng thật, cách nhau bởi dấu phẩy")
    ap.add_argument("--skip-lineage", action="store_true", help="Không ghi runs/lineage.jsonl")
    ap.add_argument("--hash-checked-by", default="", help="Tên người ĐÃ mở ảnh wrong_hash và thấy nguyên vẹn (bắt buộc nếu có wrong_hash)")
    args = ap.parse_args()

    run_dir = Path(args.run)
    rules_path = Path(args.rules) if args.rules else (run_dir / "rules.json")
    if not rules_path.is_file():
        rules_path = None
    corrupt = {s.strip() for s in args.corrupt_hash.split(",") if s.strip()}
    return build_handover(run_dir, rules_path, corrupt, skip_lineage=args.skip_lineage, hash_checked_by=args.hash_checked_by)


if __name__ == "__main__":
    raise SystemExit(main())
