#!/usr/bin/env python3
"""Validator của nhóm VINT023 cho Day 10 Lab.

Giao diện cố định:
  python3 validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]

Ràng buộc tuân thủ RULES.md:
  - Chỉ đọc thư mục delivery được truyền vào.
  - Chỉ dùng thư viện chuẩn Python 3.10+ (được import scripts/pngutil.py).
  - Không mạng, không Pillow, không đọc _private/ hay data_source/, không nhúng tên ảnh hay seed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pngutil  # noqa: E402

# ---------------------------------------------------------------------------
# Ngưỡng đã hiệu chỉnh trên lô sạch (runs/clean, pool calib) & phân tích hình học
# (Trên 50 ảnh sạch runs/clean: outside_ratio max = 0.003, iou min = 0.908,
#  center_dist max = 0.039, unmatched thing segment max area = 299 px.)
# ---------------------------------------------------------------------------
BBOX_OOB_EPS = 0.002

DUP_REL_SIZE_TOL = 0.02
DUP_PX_SHIFT_TOL = 5.0
DUP_IOU_FALLBACK = 0.85
DUP_SIZE_FALLBACK = 0.05

# Ngưỡng ứng viên đối chiếu detection <-> panoptic
STAGE1_SAME_IOU = 0.42
STAGE1_SAME_CONTAIN = 0.48

SWAP_IOU_BOTH = 0.45
SWAP_CONTAIN_BOTH = 0.60
SWAP_IOU_STRONG = 0.62
SWAP_OCCLUDED_IOU = 0.28
SWAP_OCCLUDED_CONTAIN = 0.80
SWAP_MIN_BOX_AREA = 0.0025
SWAP_MIN_SEG_PX = 350

STAGE3_LOOSE_IOU = 0.10
STAGE3_LOOSE_CONTAIN = 0.25

DRIFT_MIN_BOX_AREA = 0.0025
DRIFT_MIN_SEG_PX = 350
DRIFT_OUTSIDE_RATIO = 0.03
DRIFT_EXPAND_IOU = 0.86
DRIFT_MARGIN_SIDE = 0.04
DRIFT_CENTER_DIST = 0.06
DRIFT_OCCLUDER_EXPLAIN_RATIO = 0.35

MISSING_MIN_SEG_BBOX_AREA_NORM = 0.006
MISSING_MIN_SEG_PX = 200

MERGE_MIN_SEG_PX = 350
MERGE_MIN_BOX_OVERLAP_PX = 100
MERGE_MIN_BOX_SHARE = 0.08
MERGE_MAX_BOX_PAIR_IOU = 0.68
MERGE_MAX_SINGLE_CONTAIN = 0.94
MERGE_MIN_SECOND_CONTAIN = 0.06


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_classes(path: Path) -> list[str]:
    classes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        _, name = line.split(" ", 1)
        classes.append(name.strip())
    return classes


def bbox_iou_xywh(a: list[float], b: list[float]) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax1 + aw, bx1 + bw)
    iy2 = min(ay1 + ah, by1 + bh)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0.0 else 0.0


def box_intersection_area(a: list[float], b: list[float]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[0] + a[2], b[0] + b[2])
    iy2 = min(a[1] + a[3], b[1] + b[3])
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def parse_yolo_boxes(label_path: Path, num_classes: int, width: int, height: int) -> tuple[list[dict], bool, bool]:
    """Return (valid_boxes_px, has_invalid_class, has_oob)."""
    text = label_path.read_text(encoding="utf-8")
    boxes: list[dict] = []
    has_invalid_class = False
    has_oob = False

    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 5:
            has_invalid_class = True
            continue
        try:
            cid_f = float(parts[0])
            cx, cy, bw, bh = map(float, parts[1:5])
        except ValueError:
            has_invalid_class = True
            continue

        if not cid_f.is_integer():
            has_invalid_class = True
            continue
        cid = int(cid_f)
        if not (0 <= cid < num_classes):
            has_invalid_class = True
            continue

        x1_n = cx - bw / 2.0
        y1_n = cy - bh / 2.0
        x2_n = cx + bw / 2.0
        y2_n = cy + bh / 2.0
        if (
            bw <= 0.0
            or bh <= 0.0
            or x1_n < -BBOX_OOB_EPS
            or y1_n < -BBOX_OOB_EPS
            or x2_n > 1.0 + BBOX_OOB_EPS
            or y2_n > 1.0 + BBOX_OOB_EPS
        ):
            has_oob = True

        x1_px = max(0, min(width, int(round(x1_n * width))))
        y1_px = max(0, min(height, int(round(y1_n * height))))
        x2_px = max(0, min(width, int(round(x2_n * width))))
        y2_px = max(0, min(height, int(round(y2_n * height))))

        boxes.append({
            "cid": cid,
            "cx_n": cx,
            "cy_n": cy,
            "w_n": bw,
            "h_n": bh,
            "bbox": [x1_n * width, y1_n * height, bw * width, bh * height],
            "px_rect": (x1_px, y1_px, x2_px, y2_px),
            "norm_area": bw * bh,
            "px_area": max(1.0, (bw * width) * (bh * height)),
        })

    return boxes, has_invalid_class, has_oob


def has_duplicate_box(boxes: list[dict], width: int, height: int) -> bool:
    n = len(boxes)
    for i in range(n):
        a = boxes[i]
        for j in range(i + 1, n):
            b = boxes[j]
            if a["cid"] != b["cid"]:
                continue
            max_w = max(a["w_n"], b["w_n"], 1e-9)
            max_h = max(a["h_n"], b["h_n"], 1e-9)
            dw_rel = abs(a["w_n"] - b["w_n"]) / max_w
            dh_rel = abs(a["h_n"] - b["h_n"]) / max_h
            dx_px = abs(a["cx_n"] - b["cx_n"]) * width
            dy_px = abs(a["cy_n"] - b["cy_n"]) * height
            if dw_rel <= DUP_REL_SIZE_TOL and dh_rel <= DUP_REL_SIZE_TOL and dx_px <= DUP_PX_SHIFT_TOL and dy_px <= DUP_PX_SHIFT_TOL:
                return True
            iou = bbox_iou_xywh(a["bbox"], b["bbox"])
            if iou >= DUP_IOU_FALLBACK and dw_rel <= DUP_SIZE_FALLBACK and dh_rel <= DUP_SIZE_FALLBACK:
                return True
    return False


def count_mask_pixels(mask_path: Path, boxes: list[dict], need_boxes: bool) -> tuple[int, int, dict[int, int], list[dict[int, int]]]:
    """Read panoptic PNG once and return (W, H, total_px_by_sid, per_box_px_by_sid)."""
    w, h, pixels = pngutil.read_rgb(mask_path)
    r = bytes(pixels[0::3])
    g = bytes(pixels[1::3])
    b = bytes(pixels[2::3])

    rgb_counts = Counter(zip(r, g, b))
    total_by_sid: dict[int, int] = {}
    for (rv, gv, bv), cnt in rgb_counts.items():
        sid = rv + (gv << 8) + (bv << 16)
        if sid:
            total_by_sid[sid] = cnt

    per_box: list[dict[int, int]] = []
    if need_boxes and boxes:
        for box in boxes:
            x1, y1, x2, y2 = box["px_rect"]
            if x2 <= x1 or y2 <= y1:
                per_box.append({})
                continue
            br = bytearray()
            bg = bytearray()
            bb = bytearray()
            for y in range(y1, y2):
                s = y * w + x1
                e = y * w + x2
                br += r[s:e]
                bg += g[s:e]
                bb += b[s:e]
            box_rgb = Counter(zip(br, bg, bb))
            box_sids: dict[int, int] = {}
            for (rv, gv, bv), cnt in box_rgb.items():
                sid = rv + (gv << 8) + (bv << 16)
                if sid:
                    box_sids[sid] = cnt
            per_box.append(box_sids)
    else:
        per_box = [{} for _ in boxes]

    return w, h, total_by_sid, per_box


def _process_one_image(task: dict) -> tuple[list[tuple[str, str]], list[dict]]:
    delivery = Path(task["delivery"])
    stem = task["stem"]
    item = task["item"]
    meta = task["meta"]
    expected_guideline = task["expected_guideline"]
    pan_ann = task["pan_ann"]
    width = task["width"]
    height = task["height"]
    classes = task["classes"]
    cat_by_id = task["cat_by_id"]
    thing_cat_ids = task["thing_cat_ids"]
    cat_name_to_cid = task["cat_name_to_cid"]
    compute_candidates = task["compute_candidates"]

    rule_errors: list[tuple[str, str]] = []
    img_path = delivery / item["image"]
    lbl_path = delivery / item["label"]
    mask_path = delivery / item["mask"]

    if not img_path.is_file():
        rule_errors.append(("missing_image", stem))
    else:
        if sha256_file(img_path) != item["image_sha256"]:
            rule_errors.append(("wrong_hash", stem))

    if lbl_path.is_file() and item.get("label_sha256") and sha256_file(lbl_path) != item["label_sha256"]:
        rule_errors.append(("wrong_hash", stem))
    if mask_path.is_file() and item.get("mask_sha256") and sha256_file(mask_path) != item["mask_sha256"]:
        rule_errors.append(("wrong_hash", stem))

    if meta["guideline_version"] != expected_guideline:
        rule_errors.append(("guideline_mismatch", stem))

    boxes: list[dict] = []
    if lbl_path.is_file():
        boxes, bad_cls, oob = parse_yolo_boxes(lbl_path, len(classes), width, height)
        if bad_cls:
            rule_errors.append(("invalid_class", stem))
        if oob:
            rule_errors.append(("bbox_out_of_bounds", stem))
        if has_duplicate_box(boxes, width, height):
            rule_errors.append(("duplicate_box", stem))

    segments = pan_ann.get("segments_info", []) if pan_ann else []
    has_invalid_cat = any(seg["category_id"] not in cat_by_id for seg in segments)
    if has_invalid_cat:
        rule_errors.append(("invalid_category_id", stem))

    need_mask = mask_path.is_file()
    if not need_mask:
        return rule_errors, []

    need_box_pixels = compute_candidates and not rule_errors
    mask_w, mask_h, total_by_sid, per_box_px = count_mask_pixels(mask_path, boxes, need_box_pixels)

    for seg in segments:
        if seg["category_id"] in thing_cat_ids and not seg.get("iscrowd"):
            declared = int(seg.get("area", 0))
            actual = total_by_sid.get(seg["id"], 0)
            if declared > actual:
                rule_errors.append(("thing_overlap", stem))
                break

    if not compute_candidates or rule_errors:
        return rule_errors, []

    # -----------------------------------------------------------------------
    # Pha 2: Đối chiếu Detection <-> Panoptic để sinh ứng viên (chỉ ảnh sạch luật)
    # -----------------------------------------------------------------------
    candidates: list[dict] = []
    img_area_px = float(max(1, mask_w * mask_h))

    thing_segs: list[dict] = []
    crowd_segs: list[dict] = []
    for seg in segments:
        cat = cat_by_id.get(seg["category_id"])
        if not cat or not cat.get("isthing"):
            continue
        cname = cat["name"]
        cid = cat_name_to_cid.get(cname)
        if cid is None:
            continue
        sid = seg["id"]
        actual_area = total_by_sid.get(sid, int(seg.get("area", 0)))
        entry = {
            "id": sid,
            "cid": cid,
            "name": cname,
            "bbox": [float(v) for v in seg["bbox"]],
            "area": max(1, actual_area),
        }
        if seg.get("iscrowd"):
            crowd_segs.append(entry)
        else:
            thing_segs.append(entry)

    # Precompute box index -> {seg_id: px}
    for b_idx, box in enumerate(boxes):
        box["idx"] = b_idx
        box["name"] = classes[box["cid"]]
        box["seg_px"] = per_box_px[b_idx]

    used_boxes: set[int] = set()
    used_segs: set[int] = set()
    matched_same: list[tuple[dict, dict, float, float]] = []
    matched_same_by_seg: dict[int, int] = {}

    def greedy_match(pairs: list[tuple[float, int, int, float, float]]) -> list[tuple[int, int, float, float]]:
        pairs.sort(key=lambda item: item[0], reverse=True)
        chosen: list[tuple[int, int, float, float]] = []
        for _, bi, si, iou, contain in pairs:
            if bi in used_boxes or si in used_segs:
                continue
            used_boxes.add(bi)
            used_segs.add(si)
            chosen.append((bi, si, iou, contain))
        return chosen

    # 1. Chặng 1: ghép 1-1 cùng lớp mạnh trước (box đã ghép đúng vật riêng sẽ không gây báo nhầm instance_merge)
    stage1_pairs: list[tuple[float, int, int, float, float]] = []
    for bi, b in enumerate(boxes):
        for si, s in enumerate(thing_segs):
            if b["cid"] != s["cid"]:
                continue
            iou = bbox_iou_xywh(b["bbox"], s["bbox"])
            contain = b["seg_px"].get(s["id"], 0) / s["area"]
            if iou >= STAGE1_SAME_IOU and contain >= STAGE1_SAME_CONTAIN:
                stage1_pairs.append((iou + 0.5 * contain, bi, si, iou, contain))
    for bi, si, iou, contain in greedy_match(stage1_pairs):
        matched_same.append((boxes[bi], thing_segs[si], iou, contain))
        matched_same_by_seg[si] = bi

    # 2. Chặng 2: khác lớp trùng vị trí -> nghi ngờ class_swap hoặc category_swap
    stage2_pairs: list[tuple[float, int, int, float, float]] = []
    for bi, b in enumerate(boxes):
        if bi in used_boxes:
            continue
        for si, s in enumerate(thing_segs):
            if si in used_segs or b["cid"] == s["cid"]:
                continue
            px_overlap = b["seg_px"].get(s["id"], 0)
            iou = bbox_iou_xywh(b["bbox"], s["bbox"])
            contain = px_overlap / s["area"]
            px_share = px_overlap / b["px_area"]
            if (
                (iou >= SWAP_IOU_BOTH and contain >= SWAP_CONTAIN_BOTH)
                or (iou >= SWAP_IOU_STRONG and contain >= 0.45)
                or (iou >= SWAP_OCCLUDED_IOU and contain >= SWAP_OCCLUDED_CONTAIN and px_share >= 0.25)
            ):
                stage2_pairs.append((iou + 0.5 * contain, bi, si, iou, contain))
    for bi, si, iou, contain in greedy_match(stage2_pairs):
        b, s = boxes[bi], thing_segs[si]
        if b["norm_area"] >= SWAP_MIN_BOX_AREA or s["area"] >= SWAP_MIN_SEG_PX:
            candidates.append({
                "image": stem,
                "suggested_type": "class_swap_or_category_swap",
                "possible_types": ["class_swap", "category_swap"],
                "reason": (
                    f"Box detection '{b['name']}' trùng segment panoptic '{s['name']}' (IoU={iou:.2f}, contain={contain:.2f})"
                ),
                "severity": round(iou + contain, 3),
                "det_class": b["name"],
                "pan_class": s["name"],
                "det_bboxes": [b["bbox"]],
                "seg_id": s["id"],
                "seg_bbox": s["bbox"],
                "metrics": {
                    "iou": round(iou, 3),
                    "contain": round(contain, 3),
                    "det_norm_area": round(b["norm_area"], 4),
                    "seg_area_px": s["area"],
                },
            })

    # 3. Phát hiện instance_merge: ít nhất 1 box chưa có segment riêng cùng ăn vào segment hợp nhất
    merged_segs: set[int] = set()
    for s_idx, seg in enumerate(thing_segs):
        if seg["area"] < MERGE_MIN_SEG_PX:
            continue
        if s_idx in used_segs and s_idx not in matched_same_by_seg:
            continue
        sid = seg["id"]
        owner_bi = matched_same_by_seg.get(s_idx)

        claiming_boxes: list[tuple[dict, int]] = []
        for b in boxes:
            if b["cid"] != seg["cid"]:
                continue
            bi = b["idx"]
            if bi in used_boxes and bi != owner_bi:
                continue
            px_here = b["seg_px"].get(sid, 0)
            if px_here < MERGE_MIN_BOX_OVERLAP_PX or (px_here / b["px_area"]) < MERGE_MIN_BOX_SHARE:
                continue
            claiming_boxes.append((b, px_here))

        if len(claiming_boxes) < 2:
            continue

        best_pair = None
        best_score = -1.0
        for i in range(len(claiming_boxes)):
            b1, px1 = claiming_boxes[i]
            for j in range(i + 1, len(claiming_boxes)):
                b2, px2 = claiming_boxes[j]
                if b1["idx"] in used_boxes and b2["idx"] in used_boxes:
                    continue
                pair_iou = bbox_iou_xywh(b1["bbox"], b2["bbox"])
                if pair_iou >= MERGE_MAX_BOX_PAIR_IOU:
                    continue
                c1 = px1 / seg["area"]
                c2 = px2 / seg["area"]
                unmatched_b, unmatched_px = (b2, px2) if b2["idx"] not in used_boxes else (b1, px1)
                unmatched_fill = unmatched_px / unmatched_b["px_area"]
                if max(c1, c2) >= MERGE_MAX_SINGLE_CONTAIN and unmatched_fill < 0.30:
                    continue
                if min(c1, c2) < MERGE_MIN_SECOND_CONTAIN and min(px1, px2) < 200:
                    continue
                score = c1 + c2 - pair_iou
                if score > best_score:
                    best_score = score
                    best_pair = (b1, b2, px1, px2, pair_iou)

        if best_pair is not None:
            b1, b2, px1, px2, pair_iou = best_pair
            used_boxes.add(b1["idx"])
            used_boxes.add(b2["idx"])
            used_segs.add(s_idx)
            merged_segs.add(s_idx)
            candidates.append({
                "image": stem,
                "suggested_type": "instance_merge",
                "possible_types": ["instance_merge"],
                "reason": (
                    f"1 segment panoptic '{seg['name']}' phủ {px1}px + {px2}px trong 2 box detection tách biệt (pair_iou={pair_iou:.2f})"
                ),
                "severity": round(best_score, 3),
                "det_class": seg["name"],
                "pan_class": seg["name"],
                "det_bboxes": [b1["bbox"], b2["bbox"]],
                "seg_id": sid,
                "seg_bbox": seg["bbox"],
                "metrics": {
                    "seg_area_px": seg["area"],
                    "box1_px": px1,
                    "box2_px": px2,
                    "pair_iou": round(pair_iou, 3),
                },
            })

    if merged_segs:
        merged_ids = {thing_segs[si]["id"] for si in merged_segs}
        matched_same = [item for item in matched_same if item[1]["id"] not in merged_ids]

    # 4. Chặng 3: cùng lớp lỏng (để bắt bbox_drift lệch mạnh)
    stage3_pairs: list[tuple[float, int, int, float, float]] = []
    for bi, b in enumerate(boxes):
        if bi in used_boxes:
            continue
        for si, s in enumerate(thing_segs):
            if si in used_segs or b["cid"] != s["cid"]:
                continue
            iou = bbox_iou_xywh(b["bbox"], s["bbox"])
            contain = b["seg_px"].get(s["id"], 0) / s["area"]
            if iou >= STAGE3_LOOSE_IOU or contain >= STAGE3_LOOSE_CONTAIN:
                stage3_pairs.append((iou + 0.5 * contain, bi, si, iou, contain))
    for bi, si, iou, contain in greedy_match(stage3_pairs):
        matched_same.append((boxes[bi], thing_segs[si], iou, contain))

    # 3. Kiểm tra bbox_drift trên các cặp đã ghép cùng lớp
    for b, s, iou, contain in matched_same:
        if b["norm_area"] < DRIFT_MIN_BOX_AREA and s["area"] < DRIFT_MIN_SEG_PX:
            continue
        outside_ratio = 1.0 - contain
        bx, by, bw, bh = b["bbox"]
        sx, sy, sw, sh = s["bbox"]
        bcx, bcy = bx + bw / 2.0, by + bh / 2.0
        scx, scy = sx + sw / 2.0, sy + sh / 2.0
        center_dist = (((bcx - scx) / max(bw, sw, 1.0)) ** 2 + ((bcy - scy) / max(bh, sh, 1.0)) ** 2) ** 0.5

        m_left = max(0.0, (sx - bx) / max(bw, 1.0))
        m_right = max(0.0, ((bx + bw) - (sx + sw)) / max(bw, 1.0))
        m_top = max(0.0, (sy - by) / max(bh, 1.0))
        m_bottom = max(0.0, ((by + bh) - (sy + sh)) / max(bh, 1.0))

        # Phần box nằm ngoài seg_bbox có thể do một vật khác (occluder) đè qua vật bị chia đôi trong COCO
        other_thing_px = sum(cnt for sid, cnt in b["seg_px"].items() if sid != s["id"] and any(ts["id"] == sid for ts in thing_segs))
        non_seg_box_px = max(1.0, b["px_area"] - b["seg_px"].get(s["id"], 0))
        occluder_share = other_thing_px / non_seg_box_px

        flag_outside = outside_ratio >= DRIFT_OUTSIDE_RATIO
        flag_expand = (
            iou < DRIFT_EXPAND_IOU
            and (
                (m_left >= DRIFT_MARGIN_SIDE and m_right >= DRIFT_MARGIN_SIDE)
                or (m_top >= DRIFT_MARGIN_SIDE and m_bottom >= DRIFT_MARGIN_SIDE)
                or center_dist >= DRIFT_CENTER_DIST
            )
            and occluder_share < DRIFT_OCCLUDER_EXPLAIN_RATIO
        )
        if flag_outside or flag_expand:
            candidates.append({
                "image": stem,
                "suggested_type": "bbox_drift",
                "possible_types": ["bbox_drift"],
                "reason": (
                    f"Box '{b['name']}' lệch/chênh kích thước với segment (outside={outside_ratio:.2f}, IoU={iou:.2f}, center_dist={center_dist:.2f})"
                ),
                "severity": round(max(outside_ratio, 1.0 - iou), 3),
                "det_class": b["name"],
                "pan_class": s["name"],
                "det_bboxes": [b["bbox"]],
                "seg_id": s["id"],
                "seg_bbox": s["bbox"],
                "metrics": {
                    "outside_ratio": round(outside_ratio, 3),
                    "iou": round(iou, 3),
                    "center_dist": round(center_dist, 3),
                    "occluder_share": round(occluder_share, 3),
                },
            })

    # 4. Kiểm tra missing_box: segment thing lớn không ghép được với box cùng lớp nào
    for si, s in enumerate(thing_segs):
        if si in used_segs:
            continue
        sb_area_norm = (s["bbox"][2] * s["bbox"][3]) / img_area_px
        if sb_area_norm < MISSING_MIN_SEG_BBOX_AREA_NORM or s["area"] < MISSING_MIN_SEG_PX:
            continue

        # Bỏ qua nếu segment nằm gọn trong một box detection cùng lớp đã ghép hoặc crowd trùng vị trí
        swallowed_by_same_box = any(
            b["cid"] == s["cid"] and (b["seg_px"].get(s["id"], 0) / s["area"]) >= 0.70
            for b in boxes
        )
        if swallowed_by_same_box:
            continue

        near_crowd = any(
            cs["cid"] == s["cid"] and bbox_iou_xywh(cs["bbox"], s["bbox"]) >= 0.35
            for cs in crowd_segs
        )
        if near_crowd:
            continue

        candidates.append({
            "image": stem,
            "suggested_type": "missing_box",
            "possible_types": ["missing_box"],
            "reason": (
                f"Segment panoptic '{s['name']}' lớn ({sb_area_norm:.1%} khung ảnh, {s['area']}px) không có box detection"
            ),
            "severity": round(sb_area_norm, 4),
            "det_class": None,
            "pan_class": s["name"],
            "det_bboxes": [],
            "seg_id": s["id"],
            "seg_bbox": s["bbox"],
            "metrics": {
                "seg_bbox_norm_area": round(sb_area_norm, 4),
                "seg_area_px": s["area"],
            },
        })

    return rule_errors, candidates


def validate_delivery(delivery: Path, compute_candidates: bool, workers: int) -> tuple[list[dict], list[dict]]:
    manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta_items = json.loads((delivery / "metadata.json").read_text(encoding="utf-8"))["items"]
    meta_by_img = {m["image"]: m for m in meta_items}

    with (delivery / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {row["job_id"].strip(): row for row in csv.DictReader(f)}

    classes = load_classes(delivery / "classes.txt")
    cat_name_to_cid = {name: idx for idx, name in enumerate(classes)}

    panoptic = json.loads((delivery / "panoptic.json").read_text(encoding="utf-8"))
    cat_by_id = {c["id"]: c for c in panoptic["categories"]}
    thing_cat_ids = {c["id"] for c in panoptic["categories"] if c.get("isthing")}
    img_by_id = {im["id"]: im for im in panoptic["images"]}
    img_by_stem = {Path(im["file_name"]).stem: im for im in panoptic["images"]}
    pan_ann_by_img_id = {ann["image_id"]: ann for ann in panoptic["annotations"]}

    # Scene leak check across metadata
    scene_splits: dict[str, set[str]] = {}
    for m in meta_items:
        scene_splits.setdefault(m["scene_id"], set()).add(m["split"])

    all_rule_pairs: set[tuple[str, str]] = {
        ("scene_leak", sc) for sc, splits in scene_splits.items() if len(splits) > 1
    }

    tasks = []
    for stem in sorted(manifest):
        m = meta_by_img[stem]
        im_info = img_by_stem.get(stem)
        if im_info is None:
            continue
        tasks.append({
            "delivery": str(delivery),
            "stem": stem,
            "item": manifest[stem],
            "meta": m,
            "expected_guideline": jobs[m["job_id"]]["guideline"].strip(),
            "pan_ann": pan_ann_by_img_id.get(im_info["id"]),
            "width": int(im_info["width"]),
            "height": int(im_info["height"]),
            "classes": classes,
            "cat_by_id": cat_by_id,
            "thing_cat_ids": thing_cat_ids,
            "cat_name_to_cid": cat_name_to_cid,
            "compute_candidates": compute_candidates,
        })

    all_candidates: list[dict] = []
    if workers > 1 and len(tasks) >= 16:
        try:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                for errs, cands in ex.map(_process_one_image, tasks, chunksize=8):
                    all_rule_pairs.update(errs)
                    all_candidates.extend(cands)
        except Exception:
            all_rule_pairs = {("scene_leak", sc) for sc, splits in scene_splits.items() if len(splits) > 1}
            all_candidates = []
            for task in tasks:
                errs, cands = _process_one_image(task)
                all_rule_pairs.update(errs)
                all_candidates.extend(cands)
    else:
        for task in tasks:
            errs, cands = _process_one_image(task)
            all_rule_pairs.update(errs)
            all_candidates.extend(cands)

    errors_out = [{"type": t, "target": g} for t, g in sorted(all_rule_pairs)]
    all_candidates.sort(key=lambda c: (c["image"], c["suggested_type"], -float(c.get("severity", 0.0))))
    return errors_out, all_candidates


def main() -> int:
    ap = argparse.ArgumentParser(description="Validator bắt lỗi luật và sinh ứng viên đối chiếu detection <-> panoptic")
    ap.add_argument("delivery", help="Đường dẫn thư mục delivery/")
    ap.add_argument("--out", required=True, help="File JSON ghi danh sách lỗi luật")
    ap.add_argument("--candidates", help="File JSON ghi ứng viên lỗi gán nhãn cần xem ảnh")
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    args = ap.parse_args()

    delivery = Path(args.delivery)
    if not delivery.is_dir():
        raise SystemExit(f"Không thấy thư mục delivery: {delivery}")

    errors, candidates = validate_delivery(
        delivery,
        compute_candidates=bool(args.candidates),
        workers=max(1, args.workers),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"errors": errors}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Đã ghi {len(errors)} lỗi luật -> {out_path}")

    if args.candidates:
        cand_path = Path(args.candidates)
        cand_path.parent.mkdir(parents=True, exist_ok=True)
        by_type = Counter(c["suggested_type"] for c in candidates)
        uniq_imgs = len({c["image"] for c in candidates})
        doc = {
            "summary": {
                "total_candidates": len(candidates),
                "unique_images": uniq_imgs,
                "by_type": dict(sorted(by_type.items())),
            },
            "candidates": candidates,
        }
        cand_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Đã ghi {len(candidates)} ứng viên ({uniq_imgs} ảnh) -> {cand_path}: {dict(sorted(by_type.items()))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
