#!/usr/bin/env python3
"""Bộ unit test tổng hợp (100% dữ liệu tổng hợp, KHÔNG dùng COCO hay _private).

Chạy:
  python3 -m unittest tools/test_validator.py -v
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "validator"))
sys.path.insert(0, str(ROOT / "tools"))

import build_handover  # noqa: E402
import build_trace  # noqa: E402
import merge_member_reviews  # noqa: E402
import pngutil  # noqa: E402
import review_app  # noqa: E402
import validate  # noqa: E402


CATEGORIES = [
    {"id": 1, "name": "person", "isthing": 1},
    {"id": 3, "name": "car", "isthing": 1},
    {"id": 8, "name": "truck", "isthing": 1},
    {"id": 17, "name": "cat", "isthing": 1},
    {"id": 18, "name": "dog", "isthing": 1},
    {"id": 184, "name": "tree-merged", "isthing": 0},
]
CLASSES80 = [f"cls_{i}" for i in range(80)]
CLASSES80[0] = "person"
CLASSES80[2] = "car"
CLASSES80[7] = "truck"
CLASSES80[15] = "cat"
CLASSES80[16] = "dog"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_jpg_bytes(w: int = 120, h: int = 120, color: tuple[int, int, int] = (90, 120, 150)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def make_mask_and_segs(
    w: int,
    h: int,
    rects: list[tuple[int, int, int, int, int, int, int]],
) -> tuple[bytes, list[dict]]:
    """rects: [(sid, cat_id, x1, y1, x2, y2, iscrowd)] drawn in order (later overwrites earlier)."""
    pixels = bytearray(w * h * 3)
    for sid, _cid, x1, y1, x2, y2, _crowd in rects:
        r, g, b = pngutil.segment_rgb(sid)
        for y in range(max(0, y1), min(h, y2)):
            for x in range(max(0, x1), min(w, x2)):
                off = (y * w + x) * 3
                pixels[off : off + 3] = bytes((r, g, b))

    counts: dict[int, list[int]] = {}
    for y in range(h):
        for x in range(w):
            sid = pngutil.segment_id(pixels, (y * w + x) * 3)
            if sid:
                st = counts.setdefault(sid, [0, x, y, x, y])
                st[0] += 1
                st[1] = min(st[1], x)
                st[2] = min(st[2], y)
                st[3] = max(st[3], x)
                st[4] = max(st[4], y)

    segs = []
    for sid, cid, _x1, _y1, _x2, _y2, crowd in rects:
        if sid not in counts:
            continue
        area, minx, miny, maxx, maxy = counts[sid]
        segs.append({
            "id": sid,
            "category_id": cid,
            "area": area,
            "bbox": [minx, miny, maxx - minx + 1, maxy - miny + 1],
            "iscrowd": crowd,
        })

    tmp_buf = Path(tempfile.mkstemp(suffix=".png")[1])
    try:
        pngutil.write_rgb(tmp_buf, w, h, bytes(pixels))
        data = tmp_buf.read_bytes()
    finally:
        tmp_buf.unlink(missing_ok=True)
    return data, segs


def yolo_line(cls_id: int, x1: float, y1: float, x2: float, y2: float, w: int = 120, h: int = 120) -> str:
    bw = x2 - x1
    bh = y2 - y1
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    return f"{cls_id} {cx / w:.6f} {cy / h:.6f} {bw / w:.6f} {bh / h:.6f}"


def build_synthetic_delivery(root_run: Path, specs: list[dict], rule_class: str = "car") -> Path:
    d = root_run / "delivery"
    for sub in ("images", "labels", "masks", "guideline", "incoming"):
        (d / sub).mkdir(parents=True, exist_ok=True)

    (d / "classes.txt").write_text("".join(f"{i} {n}\n" for i, n in enumerate(CLASSES80)), encoding="utf-8")

    jobs = [
        {"job_id": "J01", "annotator": "A01", "reviewer": "Q01", "guideline": "v1.2"},
        {"job_id": "J02", "annotator": "A02", "reviewer": "Q02", "guideline": "v1.2"},
        {"job_id": "J03", "annotator": "A03", "reviewer": "Q03", "guideline": "v1.3"},
    ]
    with (d / "jobs.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["job_id", "annotator", "reviewer", "guideline"])
        w.writeheader()
        w.writerows(jobs)
    job_map = {j["job_id"]: j for j in jobs}

    manifest = {}
    meta_items = []
    pan_imgs = []
    pan_anns = []

    for idx, sp in enumerate(specs, start=1):
        name = sp["name"]
        w, h = sp.get("w", 120), sp.get("h", 120)
        jpg_bytes = make_jpg_bytes(w, h)
        if not sp.get("missing_image"):
            (d / "images" / f"{name}.jpg").write_bytes(jpg_bytes)

        lbl_text = "\n".join(sp.get("yolo", [])) + ("\n" if sp.get("yolo") else "")
        lbl_bytes = lbl_text.encode("utf-8")
        (d / "labels" / f"{name}.txt").write_bytes(lbl_bytes)

        mask_bytes, segs = make_mask_and_segs(w, h, sp.get("segs", []))
        if sp.get("override_segs") is not None:
            segs = sp["override_segs"]
        (d / "masks" / f"{name}.png").write_bytes(mask_bytes)

        manifest[name] = {
            "image": f"images/{name}.jpg",
            "label": f"labels/{name}.txt",
            "mask": f"masks/{name}.png",
            "image_sha256": sp.get("fake_hash") or sha(jpg_bytes),
            "label_sha256": sha(lbl_bytes),
            "mask_sha256": sha(mask_bytes),
        }
        job_id = sp.get("job_id", "J03")
        meta_items.append({
            "image": name,
            "scene_id": sp.get("scene_id", f"scene_{100 + idx // 5}"),
            "split": sp.get("split", "train"),
            "job_id": job_id,
            "guideline_version": sp.get("guideline_version", job_map[job_id]["guideline"]),
        })
        pan_imgs.append({"id": idx, "file_name": f"{name}.jpg", "width": w, "height": h})
        pan_anns.append({"image_id": idx, "file_name": f"{name}.png", "segments_info": segs})

    pan_doc = {"categories": CATEGORIES, "images": pan_imgs, "annotations": pan_anns}
    (d / "panoptic.json").write_text(json.dumps(pan_doc) + "\n", encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"dataset": "lab250", "num_classes": 80, "items": manifest}, indent=1) + "\n", encoding="utf-8")
    (d / "metadata.json").write_text(json.dumps({"items": meta_items}, indent=1) + "\n", encoding="utf-8")
    (d / "guideline" / "changelog.md").write_text(
        f"# Changelog\n\n## v1.3\n- Lớp `{rule_class}`: vật bị che >50% vẫn gán box.\n\n## v1.2\n- Cũ.\n",
        encoding="utf-8",
    )
    reported = sp_reported = sorted({sp.get("scene_id", "scene_100") for sp in specs if sp.get("reported")}) or ["scene_100"]
    (d / "incoming" / "ticket.md").write_text(
        f"# Ticket\nBỏ sót `{rule_class}` tại {' và '.join(sp_reported)}.\n",
        encoding="utf-8",
    )
    rid = "lab250_" + sha((d / "manifest.json").read_bytes() + (d / "metadata.json").read_bytes())[:12]
    (d / "release.json").write_text(
        json.dumps({"release_id": rid, "version": "v1", "panoptic_sha256": sha((d / "panoptic.json").read_bytes())}, indent=2) + "\n",
        encoding="utf-8",
    )
    return d


class SyntheticSuiteTest(unittest.TestCase):
    def test_clean_and_occluded_has_zero_errors_and_zero_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "clean"
            specs = [
                {
                    "name": "clean_01",
                    "yolo": [yolo_line(2, 10, 10, 70, 70), yolo_line(0, 35, 20, 65, 75)],
                    "segs": [(101, 3, 10, 10, 70, 70, 0), (102, 1, 35, 20, 65, 75, 0)],
                },
                {
                    "name": "clean_02",
                    "yolo": [yolo_line(15, 20, 20, 60, 60)],
                    "segs": [(201, 17, 20, 20, 60, 60, 0)],
                },
            ]
            d = build_synthetic_delivery(run, specs)
            errs, cands = validate.validate_delivery(d, compute_candidates=True, workers=1)
            self.assertEqual(errs, [])
            self.assertEqual(cands, [])

    def test_all_9_rule_faults(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "rules"
            specs = [
                {"name": "img_missing", "missing_image": True, "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(10, 1, 10, 10, 50, 50, 0)]},
                {"name": "img_hash", "fake_hash": "0" * 64, "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(11, 1, 10, 10, 50, 50, 0)]},
                {"name": "img_badcls", "yolo": ["80 0.5 0.5 0.2 0.2"], "segs": [(12, 1, 10, 10, 50, 50, 0)]},
                {"name": "img_oob", "yolo": [yolo_line(0, 80, 10, 123, 50)], "segs": [(13, 1, 80, 10, 120, 50, 0)]},
                {"name": "img_dup", "yolo": [yolo_line(0, 10, 10, 24, 24), yolo_line(0, 12, 11, 26, 25)], "segs": [(14, 1, 10, 10, 24, 24, 0)]},
                {"name": "img_gm", "job_id": "J01", "guideline_version": "v1.3", "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(15, 1, 10, 10, 50, 50, 0)]},
                {"name": "img_leak_a", "scene_id": "scene_777", "split": "train", "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(16, 1, 10, 10, 50, 50, 0)]},
                {"name": "img_leak_b", "scene_id": "scene_777", "split": "val", "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(17, 1, 10, 10, 50, 50, 0)]},
                {"name": "img_badcat", "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(18, 999, 10, 10, 50, 50, 0)]},
                {
                    "name": "img_overlap",
                    "yolo": [yolo_line(0, 10, 10, 50, 50)],
                    "segs": [(19, 1, 10, 10, 50, 50, 0)],
                    "override_segs": [{"id": 19, "category_id": 1, "area": 1800, "bbox": [10, 10, 40, 40], "iscrowd": 0}],
                },
            ]
            d = build_synthetic_delivery(run, specs)
            errs, cands = validate.validate_delivery(d, compute_candidates=True, workers=1)
            got = {(e["type"], e["target"]) for e in errs}
            expected = {
                ("missing_image", "img_missing"),
                ("wrong_hash", "img_hash"),
                ("invalid_class", "img_badcls"),
                ("bbox_out_of_bounds", "img_oob"),
                ("duplicate_box", "img_dup"),
                ("guideline_mismatch", "img_gm"),
                ("scene_leak", "scene_777"),
                ("invalid_category_id", "img_badcat"),
                ("thing_overlap", "img_overlap"),
            }
            self.assertEqual(got, expected)
            self.assertEqual(cands, [])

    def test_all_5_semantic_candidate_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "sem"
            specs = [
                # class_swap / category_swap: det=car(2), pan=truck(8)
                {"name": "sem_swap", "yolo": [yolo_line(2, 15, 15, 85, 85)], "segs": [(101, 8, 15, 15, 85, 85, 0)]},
                # bbox_drift (shift): shifted 20px right
                {"name": "sem_drift_shift", "yolo": [yolo_line(2, 35, 20, 95, 80)], "segs": [(102, 3, 15, 20, 75, 80, 0)]},
                # bbox_drift (expand): box inflated on both sides with no occluder
                {"name": "sem_drift_expand", "yolo": [yolo_line(2, 10, 10, 95, 95)], "segs": [(103, 3, 25, 25, 80, 80, 0)]},
                # missing_box: large segment without box
                {"name": "sem_missing", "yolo": [yolo_line(0, 5, 5, 25, 45)], "segs": [(104, 1, 5, 5, 25, 45, 0), (105, 3, 40, 40, 105, 105, 0)]},
                # instance_merge: 2 separate car boxes sharing 1 merged car segment
                {
                    "name": "sem_merge",
                    "yolo": [yolo_line(2, 10, 30, 50, 80), yolo_line(2, 60, 30, 100, 80)],
                    "segs": [(106, 3, 10, 30, 100, 80, 0)],
                },
            ]
            d = build_synthetic_delivery(run, specs)
            errs, cands = validate.validate_delivery(d, compute_candidates=True, workers=1)
            self.assertEqual(errs, [])
            by_img = {c["image"]: c for c in cands}
            self.assertEqual(by_img["sem_swap"]["suggested_type"], "class_swap_or_category_swap")
            self.assertEqual(by_img["sem_drift_shift"]["suggested_type"], "bbox_drift")
            self.assertEqual(by_img["sem_drift_expand"]["suggested_type"], "bbox_drift")
            self.assertEqual(by_img["sem_missing"]["suggested_type"], "missing_box")
            self.assertEqual(by_img["sem_merge"]["suggested_type"], "instance_merge")

    def test_trace_and_full_handover_pass_check_handover(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp) / "runs"
            run = runs_root / "r99"
            specs = [
                # Job J01 (v1.2), reported scene_100 -> tier_a
                {"name": "im_01", "job_id": "J01", "scene_id": "scene_100", "reported": True, "split": "train",
                 "yolo": [yolo_line(2, 10, 10, 70, 70)], "segs": [(11, 3, 10, 10, 70, 70, 0)]},
                # Job J02 (v1.2), unreported scene_101, even with guideline_mismatch=v1.3 in metadata -> MUST be tier_b!
                {"name": "im_02", "job_id": "J02", "scene_id": "scene_101", "guideline_version": "v1.3", "split": "train",
                 "yolo": [yolo_line(2, 10, 10, 70, 70)], "segs": [(12, 3, 10, 10, 70, 70, 0)]},
                # Job J03 (v1.3), even with guideline_mismatch=v1.2 in metadata -> MUST NOT be in trace!
                {"name": "im_03", "job_id": "J03", "scene_id": "scene_102", "guideline_version": "v1.2", "split": "val",
                 "yolo": [yolo_line(2, 10, 10, 70, 70)], "segs": [(13, 3, 10, 10, 70, 70, 0)]},
                # Wrong hash (intact image -> stays in v2)
                {"name": "im_04", "job_id": "J03", "scene_id": "scene_102", "fake_hash": "a" * 64, "split": "val",
                 "yolo": [yolo_line(0, 15, 15, 75, 95)], "segs": [(14, 1, 15, 15, 75, 95, 0)]},
                # Scene leak in scene_102 (4 val vs 1 train -> majority val)
                {"name": "im_05", "job_id": "J03", "scene_id": "scene_102", "split": "val",
                 "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(15, 1, 10, 10, 50, 50, 0)]},
                {"name": "im_06", "job_id": "J03", "scene_id": "scene_102", "split": "train",
                 "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(16, 1, 10, 10, 50, 50, 0)]},
                {"name": "im_07", "job_id": "J03", "scene_id": "scene_102", "split": "val",
                 "yolo": [yolo_line(0, 10, 10, 50, 50)], "segs": [(17, 1, 10, 10, 50, 50, 0)]},
                # Class swap (det rework -> leaves v2)
                {"name": "im_08", "job_id": "J03", "scene_id": "scene_103", "split": "train",
                 "yolo": [yolo_line(2, 15, 15, 85, 85)], "segs": [(18, 8, 15, 15, 85, 85, 0)]},
                # Category swap (panoptic only -> stays in v2!)
                {"name": "im_09", "job_id": "J03", "scene_id": "scene_103", "split": "train",
                 "yolo": [yolo_line(7, 15, 15, 85, 85)], "segs": [(19, 3, 15, 15, 85, 85, 0)]},
            ]
            d = build_synthetic_delivery(runs_root / "r99", specs, rule_class="car")

            # 1. Validate rules + candidates
            errs, cands = validate.validate_delivery(d, compute_candidates=True, workers=1)
            (run / "rules.json").write_text(json.dumps({"errors": errs}, indent=2) + "\n", encoding="utf-8")
            (run / "candidates.json").write_text(json.dumps({"candidates": cands}, indent=2) + "\n", encoding="utf-8")

            # 2. Trace
            trace, _ = build_trace.build_trace(d)
            self.assertEqual(trace["tier_a"], ["im_01"])
            self.assertEqual(trace["tier_b"], ["im_02"])
            self.assertEqual(trace["notify"], ["A01", "A02", "Q01", "Q02"])
            (run / "trace.json").write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")

            # 3. Merge member reviews (simulate 2 members)
            r1 = run / "r_m1.csv"
            r2 = run / "r_m2.csv"
            r1.write_text('image,type,verdict,note\nim_08,class_swap,confirmed,"mo anh: thay xe tai lon nhung detection gan nham car"\n', encoding="utf-8")
            r2.write_text('image,type,verdict,note\nim_09,category_swap,confirmed,"mo anh: dung la xe tai lon, panoptic gan nham car"\n', encoding="utf-8")
            merge_member_reviews.merge_reviews([r1, r2], run / "review_log.csv")

            # 4. Security.md (matches H17)
            (run / "security.md").write_text(
                "# Bao mat\n\n"
                "## 1. Ca USB\n"
                "Khong chep du lieu ra USB ca nhan hay gui email ca nhan hay nho nguoi ngoai lam ho, ma phai bao quan ly va lam viec tren ha tang duoc cap phep.\n\n"
                "## 2. Nam viec\n"
                "Chi duoc mo job duoc giao tren may cong ty duoc cap quyen; khong chup man hinh gui nguoi quen, khong chep USB, khong dan nhan len AI, khong chia se tai khoan.\n\n"
                "## 3. Ca khuôn mặt\n"
                "Ket luan Hold va bao nguoi phu trach khi thay khuon mat nguoi ro trong lo, tuyet doi khong tu y xoa hay lam mo anh goc nhu im_04 trong lo nay.\n",
                encoding="utf-8",
            )

            # 5. Build handover: phải chặn nếu có wrong_hash mà chưa có tên người mở ảnh kiểm
            with self.assertRaises(SystemExit):
                build_handover.build_handover(run, run / "rules.json", set(), skip_lineage=False)

            rc = build_handover.build_handover(
                run, run / "rules.json", set(), skip_lineage=False, hash_checked_by="Vo Tien Phat"
            )
            self.assertEqual(rc, 0)

            # 6. Smoke test review_app panel renderer, wrong_hash checker & H3 raw-note guard
            manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
            wh = review_app.check_wrong_hash_images(d, manifest, run / "rules.json")
            self.assertEqual(wh[0]["status"], "intact")
            for mode in ("full", "crop_raw", "crop_overlay"):
                png_bytes = review_app.render_candidate_panel(d, manifest, cands[0], mode)
                self.assertTrue(png_bytes.startswith(b"\x89PNG"))

            state = review_app.ReviewState(
                d, run / "candidates.json", run / "review_ui_test.csv", run / "rules.json", members=5
            )
            with self.assertRaises(ValueError):
                state.save_review("im_08", "class_swap", "confirmed", "[Nguyen Hoang Nhan] ok")
            saved = state.save_review(
                "im_08", "class_swap", "confirmed", "[Nguyen Hoang Nhan] mo anh thay xe tai thung kin mau do"
            )
            self.assertEqual(len(saved), 1)


if __name__ == "__main__":
    unittest.main()
