#!/usr/bin/env python3
"""Điều phối đề ẩn (40 phút cuối buổi):

1. Chuẩn bị nhanh sau khi giải nén de_an.zip vào ./delivery/:
   python3 tools/run_de_an.py prepare [--launch-ui]

2. Sau khi cả 5 người review xong submission/de_an/review_log.csv:
   python3 tools/run_de_an.py finalize
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import metrics  # noqa: E402


def run_cmd(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def cmd_prepare(delivery: Path, members: int, launch_ui: bool, lan: bool = False) -> int:
    if not delivery.is_dir() or not (delivery / "manifest.json").is_file():
        raise SystemExit(f"Không thấy thư mục đề ẩn hợp lệ tại: {delivery} (hãy giải nén de_an.zip vào gốc repo)")

    sub_de_an = ROOT / "submission" / "de_an"
    sub_de_an.mkdir(parents=True, exist_ok=True)
    work_de_an = ROOT / "runs" / "de_an"
    work_de_an.mkdir(parents=True, exist_ok=True)

    rules_out = work_de_an / "rules.json"
    cands_out = sub_de_an / "candidates.json"
    trace_out = sub_de_an / "trace.json"
    review_csv = sub_de_an / "review_log.csv"

    run_cmd([
        sys.executable, str(ROOT / "validator" / "validate.py"),
        str(delivery), "--out", str(rules_out), "--candidates", str(cands_out),
    ])
    run_cmd([
        sys.executable, str(ROOT / "tools" / "build_trace.py"),
        "--delivery", str(delivery), "--out", str(trace_out),
    ])

    rules_data = json.loads(rules_out.read_text(encoding="utf-8"))
    cands_data = json.loads(cands_out.read_text(encoding="utf-8"))
    cands = cands_data.get("candidates", [])
    by_type = Counter(c.get("suggested_type", "?") for c in cands)
    unique_imgs = sorted({c["image"] for c in cands})

    print("\n" + "=" * 60)
    print(f"CHUẨN BỊ ĐỀ ẨN HOÀN TẤT")
    print(f"- Lỗi luật phát hiện : {len(rules_data.get('errors', []))} -> {rules_out}")
    print(f"- Ứng viên cần xem   : {len(cands)} ứng viên trên {len(unique_imgs)} ảnh -> {cands_out}")
    print(f"  Chi tiết theo loại : {dict(by_type)}")
    print(f"- Truy vết (Pha 5)   : {trace_out}")
    print(f"- Chia đều {members} thành viên:")
    for idx in range(members):
        shard_imgs = unique_imgs[idx::members]
        print(f"  + TV {idx + 1}: {len(shard_imgs)} ảnh")
    print("=" * 60)

    if launch_ui:
        ui_cmd = [
            sys.executable, str(ROOT / "tools" / "review_app.py"),
            "--delivery", str(delivery),
            "--candidates", str(cands_out),
            "--out", str(review_csv),
            "--rules", str(rules_out),
            "--members", str(members),
        ]
        if lan:
            ui_cmd += ["--host", "0.0.0.0"]
        run_cmd(ui_cmd)
    else:
        lan_flag = " --host 0.0.0.0" if lan else ""
        print(
            "\nBước tiếp theo — mở giao diện xem ảnh:\n"
            f"  python3 tools/review_app.py --delivery {delivery} --candidates {cands_out} "
            f"--out {review_csv} --rules {rules_out} --members {members}{lan_flag}"
        )
    return 0


def cmd_finalize(delivery: Path) -> int:
    sub_de_an = ROOT / "submission" / "de_an"
    rules_path = ROOT / "runs" / "de_an" / "rules.json"
    review_path = sub_de_an / "review_log.csv"
    errors_path = sub_de_an / "errors.json"
    cands_path = sub_de_an / "candidates.json"
    trace_path = sub_de_an / "trace.json"

    for p in (rules_path, review_path, cands_path, trace_path):
        if not p.is_file():
            raise SystemExit(f"Thiếu file: {p}. Hãy chạy 'prepare' và hoàn tất review trước.")

    with review_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{review_path} chưa có dòng nào.")

    short = [r.get("image") for r in rows if len((r.get("note") or "").strip()) < 20]
    if short:
        raise SystemExit(f"H3 lỗi: có {len(short)} dòng có ghi chú < 20 ký tự (ví dụ: {short[:5]}). Hãy sửa trước khi chốt!")

    notes = [(r.get("note") or "").strip() for r in rows]
    if len(set(notes)) < 0.7 * len(notes):
        raise SystemExit("H3 lỗi: ghi chú trùng lặp quá nhiều (< 70% khác nhau).")

    bad_conf = [
        r for r in rows
        if r.get("verdict", "").strip() == "confirmed" and r.get("type", "").strip() not in metrics.SEMANTIC_TYPES
    ]
    if bad_conf:
        raise SystemExit(f"Có dòng confirmed sai loại lỗi: {bad_conf[:3]}")

    cands = json.loads(cands_path.read_text(encoding="utf-8")).get("candidates", [])
    reviewed_imgs = {r.get("image", "").strip() for r in rows}
    unreviewed = sorted({c["image"] for c in cands} - reviewed_imgs)
    if unreviewed:
        print(f"[Cảnh báo] Còn {len(unreviewed)} ảnh trong candidates.json chưa có trong review_log.csv: {unreviewed[:10]}")

    run_cmd([
        sys.executable, str(SCRIPTS / "merge_review.py"),
        "--rules", str(rules_path), "--review", str(review_path), "--out", str(errors_path),
    ])

    err_doc = json.loads(errors_path.read_text(encoding="utf-8"))
    trace_doc = json.loads(trace_path.read_text(encoding="utf-8"))
    for k in ("tier_a", "tier_b", "notify"):
        if not isinstance(trace_doc.get(k), list):
            raise SystemExit(f"trace.json thiếu hoặc sai kiểu ở khoá {k}")

    # Verify delivery/ is ignored by git
    git_check = subprocess.run(
        ["git", "status", "--porcelain", str(delivery)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if git_check.stdout.strip():
        print(f"[CẢNH BÁO] git thấy thay đổi chưa ignore ở {delivery}: {git_check.stdout.strip()}")

    print(
        "\nĐỀ ẨN ĐÃ CHỐT XONG:\n"
        f"  - {errors_path}: {len(err_doc['errors'])} lỗi\n"
        f"  - {review_path}: {len(rows)} dòng review\n"
        f"  - {cands_path}: {len(cands)} ứng viên\n"
        f"  - {trace_path}: tier_a={len(trace_doc['tier_a'])}, tier_b={len(trace_doc['tier_b'])}, notify={len(trace_doc['notify'])}\n"
        "Bước cuối: git add submission/de_an && git commit -m \"P6: hoan thanh de an\" && git push"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Điều phối nhanh đề ẩn 40 phút")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare", help="Chạy validator + build_trace trên delivery/ của đề ẩn")
    p_prep.add_argument("--delivery", default="delivery")
    p_prep.add_argument("--members", type=int, default=5)
    p_prep.add_argument("--launch-ui", action="store_true")
    p_prep.add_argument("--lan", action="store_true", help="Mở Web UI qua 0.0.0.0 để 5 máy cùng xem qua LAN")

    p_fin = sub.add_parser("finalize", help="Kiểm tra H3, gộp errors.json và xác nhận submission/de_an/")
    p_fin.add_argument("--delivery", default="delivery")

    args = ap.parse_args()
    delivery = ROOT / args.delivery if not Path(args.delivery).is_absolute() else Path(args.delivery)
    if args.cmd == "prepare":
        return cmd_prepare(delivery, args.members, args.launch_ui, lan=args.lan)
    return cmd_finalize(delivery)


if __name__ == "__main__":
    raise SystemExit(main())
