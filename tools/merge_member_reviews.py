#!/usr/bin/env python3
"""Gộp nhiều file review_log_*.csv từ các thành viên thành 1 file review_log.csv chuẩn H3.

Usage:
  python3 tools/merge_member_reviews.py runs/r23007/review_m1.csv runs/r23007/review_m2.csv --out runs/r23007/review_log.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import metrics  # noqa: E402


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"image", "type", "verdict", "note"}
        if not reader.fieldnames or not required.issubset({c.strip() for c in reader.fieldnames}):
            raise SystemExit(f"{path}: thiếu cột bắt buộc {sorted(required)}, thấy {reader.fieldnames}")
        rows = []
        for idx, raw in enumerate(reader, start=2):
            row = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
            if not any(row.values()):
                continue
            if not row["image"] or not row["type"] or row["verdict"] not in ("confirmed", "rejected"):
                raise SystemExit(f"{path}:{idx}: dòng không hợp lệ (cần image, type, verdict in confirmed/rejected): {row}")
            if row["verdict"] == "confirmed" and row["type"] not in metrics.SEMANTIC_TYPES:
                raise SystemExit(f"{path}:{idx}: confirmed type '{row['type']}' không thuộc SEMANTIC_TYPES {sorted(metrics.SEMANTIC_TYPES)}")
            row["_source"] = f"{path.name}:{idx}"
            rows.append(row)
        return rows


def merge_reviews(inputs: list[Path], out_path: Path, prefer_last: bool = False) -> None:
    merged: dict[tuple[str, str], dict[str, str]] = {}
    conflicts: list[str] = []

    for path in inputs:
        if not path.is_file():
            raise SystemExit(f"Không thấy file review: {path}")
        for row in load_rows(path):
            key = (row["image"], row["type"])
            if key in merged:
                prev = merged[key]
                if prev["verdict"] != row["verdict"]:
                    msg = (
                        f"Xung đột {key}: {prev['_source']} ghi {prev['verdict']} "
                        f"vs {row['_source']} ghi {row['verdict']}"
                    )
                    if not prefer_last:
                        conflicts.append(msg)
                        continue
                    print(f"[Cảnh báo] {msg} (chọn bản sau)", file=sys.stderr)
                elif len(row["note"]) <= len(prev["note"]):
                    continue
            merged[key] = row

    if conflicts:
        raise SystemExit("Phát hiện xung đột khi gộp review (dùng --prefer-last hoặc sửa tay):\n  - " + "\n  - ".join(conflicts))

    final_rows = sorted(merged.values(), key=lambda r: (r["image"], r["type"]))
    if not final_rows:
        raise SystemExit("Không có dòng review nào hợp lệ sau khi gộp.")

    short_notes = [f"{r['_source']} ({r['image']}, len={len(r['note'])})" for r in final_rows if len(r["note"]) < 20]
    if short_notes:
        raise SystemExit(
            "Lỗi H3: có ghi chú ngắn hơn 20 ký tự (sẽ FAIL check_handover):\n  - " + "\n  - ".join(short_notes)
        )

    notes = [r["note"] for r in final_rows]
    unique_ratio = len(set(notes)) / len(notes)
    if unique_ratio < 0.7:
        raise SystemExit(
            f"Lỗi H3: tỉ lệ ghi chú khác nhau quá thấp ({len(set(notes))}/{len(notes)} = {unique_ratio:.0%}, cần >= 70%)."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "type", "verdict", "note"])
        writer.writeheader()
        for r in final_rows:
            writer.writerow({k: r[k] for k in ("image", "type", "verdict", "note")})

    n_conf = sum(1 for r in final_rows if r["verdict"] == "confirmed")
    n_rej = len(final_rows) - n_conf
    print(f"Đã gộp {len(final_rows)} dòng ({n_conf} confirmed, {n_rej} rejected) -> {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Gộp các file review_log CSV từ nhiều thành viên")
    ap.add_argument("inputs", nargs="+", help="Các file CSV đầu vào")
    ap.add_argument("--out", required=True, help="File review_log.csv đầu ra")
    ap.add_argument("--prefer-last", action="store_true", help="Nếu trùng (image, type) khác verdict thì lấy file sau")
    args = ap.parse_args()

    merge_reviews([Path(p) for p in args.inputs], Path(args.out), prefer_last=args.prefer_last)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
