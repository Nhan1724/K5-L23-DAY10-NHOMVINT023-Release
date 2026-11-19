#!/usr/bin/env python3
"""Phase 2 & De An visual review workbench (Python stdlib + Pillow, NEVER reads _private).

Features:
  - Tab 1: Review cross-check candidates (full overlay + RAW zoomed crop + OVERLAY zoomed crop)
           Supports 5-member deterministic sharding, per-member CSV export, and live H3 guards.
  - Tab 2: Check wrong_hash image integrity (Pha 4) & browse largest 'person' images for security.md (Pha 6).

Usage:
  python3 tools/review_app.py --delivery runs/r23007/delivery --candidates runs/r23007/candidates.json --out runs/r23007/review_log.csv --rules runs/r23007/rules.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import socket
import sys
import threading
import urllib.parse
import webbrowser
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
except ImportError as exc:
    raise SystemExit("Cần Pillow để chạy công cụ xem ảnh (pip install pillow). Validator không dùng Pillow.") from exc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import metrics  # noqa: E402
import pngutil  # noqa: E402


def load_classes(delivery: Path) -> list[str]:
    return [
        line.split(" ", 1)[1].strip()
        for line in (delivery / "classes.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def segment_binary_mask(mask_path: Path, seg_id: int) -> Image.Image:
    """Return 'L' mode binary mask (0 or 255) for seg_id using fast Pillow C ops."""
    r, g, b = pngutil.segment_rgb(seg_id)
    mask_rgb = Image.open(mask_path).convert("RGB")
    ch_r, ch_g, ch_b = mask_rgb.split()
    mr = ch_r.point(lambda x: 255 if x == r else 0)
    mg = ch_g.point(lambda x: 255 if x == g else 0)
    mb = ch_b.point(lambda x: 255 if x == b else 0)
    return ImageChops.darker(ImageChops.darker(mr, mg), mb)


def _draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, bg: tuple[int, int, int]) -> None:
    x, y = xy
    tw = max(40, len(text) * 7 + 8)
    th = 16
    y_box = max(0, y - th)
    draw.rectangle([x, y_box, x + tw, y_box + th], fill=bg)
    draw.text((x + 4, y_box + 2), text, fill=(0, 0, 0))


def _clamp_crop_box(w: int, h: int, boxes: list[list[float]]) -> tuple[int, int, int, int]:
    if not boxes:
        return (0, 0, w, h)
    x1 = min(b[0] for b in boxes)
    y1 = min(b[1] for b in boxes)
    x2 = max(b[0] + b[2] for b in boxes)
    y2 = max(b[1] + b[3] for b in boxes)
    bw = max(20.0, x2 - x1)
    bh = max(20.0, y2 - y1)
    pad_x = max(28.0, bw * 0.40)
    pad_y = max(28.0, bh * 0.40)
    cx1 = max(0, int(x1 - pad_x))
    cy1 = max(0, int(y1 - pad_y))
    cx2 = min(w, int(x2 + pad_x))
    cy2 = min(h, int(y2 + pad_y))
    if cx2 - cx1 < 64:
        cx1 = max(0, (cx1 + cx2) // 2 - 32)
        cx2 = min(w, cx1 + 64)
    if cy2 - cy1 < 64:
        cy1 = max(0, (cy1 + cy2) // 2 - 32)
        cy2 = min(h, cy1 + 64)
    return (cx1, cy1, cx2, cy2)


def render_candidate_panel(delivery: Path, manifest: dict, cand: dict, mode: str) -> bytes:
    """Render 'full', 'crop_raw', or 'crop_overlay' PNG bytes for a candidate."""
    stem = cand["image"]
    item = manifest[stem]
    img_path = delivery / item["image"]
    mask_path = delivery / item["mask"]

    base = ImageOps.exif_transpose(Image.open(img_path)).convert("RGB")
    w, h = base.size

    det_boxes = cand.get("det_bboxes") or []
    seg_bbox = cand.get("seg_bbox")
    all_boxes = [list(b) for b in det_boxes]
    if seg_bbox:
        all_boxes.append(list(seg_bbox))

    crop_box = _clamp_crop_box(w, h, all_boxes)

    if mode == "crop_raw":
        crop = base.crop(crop_box)
        scale = min(4.0, max(1.0, 440.0 / max(crop.size)))
        new_size = (max(1, int(crop.width * scale)), max(1, int(crop.height * scale)))
        out = crop.resize(new_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()

    overlay_img = base.convert("RGBA")
    seg_id = cand.get("seg_id")
    if seg_id and mask_path.is_file():
        seg_mask = segment_binary_mask(mask_path, int(seg_id))
        tint = Image.new("RGBA", (w, h), (255, 42, 133, 75))
        empty = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        overlay_img = Image.alpha_composite(overlay_img, Image.composite(tint, empty, seg_mask))
        # Sharp magenta border
        dilated = seg_mask.filter(ImageFilter.MaxFilter(3))
        edge = ImageChops.subtract(dilated, seg_mask)
        edge_layer = Image.new("RGBA", (w, h), (255, 42, 133, 240))
        overlay_img = Image.alpha_composite(overlay_img, Image.composite(edge_layer, empty, edge))

    if mode == "crop_overlay":
        crop = overlay_img.crop(crop_box).convert("RGB")
        scale = min(4.0, max(1.0, 440.0 / max(crop.size)))
        new_size = (max(1, int(crop.width * scale)), max(1, int(crop.height * scale)))
        out = crop.resize(new_size, Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(out)
        sx, sy = new_size[0] / (crop_box[2] - crop_box[0]), new_size[1] / (crop_box[3] - crop_box[1])
        if seg_bbox:
            bx = (seg_bbox[0] - crop_box[0]) * sx
            by = (seg_bbox[1] - crop_box[1]) * sy
            bw = seg_bbox[2] * sx
            bh = seg_bbox[3] * sy
            draw.rectangle([bx, by, bx + bw, by + bh], outline=(255, 110, 180), width=2)
            _draw_label(draw, (int(bx), int(by + bh + 16)), f"PAN: {cand.get('pan_class') or ''}", (255, 140, 200))
        for idx, b in enumerate(det_boxes):
            bx = (b[0] - crop_box[0]) * sx
            by = (b[1] - crop_box[1]) * sy
            bw = b[2] * sx
            bh = b[3] * sy
            color = (0, 229, 255) if idx == 0 else (255, 214, 0)
            draw.rectangle([bx, by, bx + bw, by + bh], outline=color, width=3)
            _draw_label(draw, (int(bx), int(by)), f"DET: {cand.get('det_class') or ''}", color)
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()

    # mode == "full"
    out = overlay_img.convert("RGB")
    draw = ImageDraw.Draw(out)
    if seg_bbox:
        bx, by, bw, bh = seg_bbox
        draw.rectangle([bx, by, bx + bw, by + bh], outline=(255, 110, 180), width=2)
    for idx, b in enumerate(det_boxes):
        bx, by, bw, bh = b
        color = (0, 229, 255) if idx == 0 else (255, 214, 0)
        draw.rectangle([bx, by, bx + bw, by + bh], outline=color, width=3)
        _draw_label(draw, (int(bx), int(by)), f"DET: {cand.get('det_class') or ''}", color)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def check_wrong_hash_images(delivery: Path, manifest: dict, rules_path: Path | None) -> list[dict]:
    if not rules_path or not rules_path.is_file():
        return []
    errors = json.loads(rules_path.read_text(encoding="utf-8")).get("errors", [])
    out = []
    for err in errors:
        if err.get("type") != "wrong_hash":
            continue
        stem = err["target"]
        item = manifest.get(stem, {})
        img_path = delivery / item.get("image", f"images/{stem}.jpg")
        status = "missing"
        dims = ""
        size_kb = 0.0
        if img_path.is_file():
            size_kb = round(img_path.stat().st_size / 1024.0, 1)
            try:
                with Image.open(img_path) as im:
                    im.verify()
                with Image.open(img_path) as im2:
                    im2.load()
                    dims = f"{im2.width}x{im2.height}"
                status = "intact"
            except Exception as exc:
                status = f"corrupt: {exc}"
        out.append({"image": stem, "status": status, "dims": dims, "size_kb": size_kb})
    return out


def find_person_candidates(delivery: Path, manifest: dict, classes: list[str], limit: int = 16) -> list[dict]:
    if "person" not in classes:
        return []
    person_id = classes.index("person")
    scored = []
    for stem, item in manifest.items():
        lbl_path = delivery / item["label"]
        if not lbl_path.is_file() or not (delivery / item["image"]).is_file():
            continue
        areas = []
        for line in lbl_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                cid = int(float(parts[0]))
                w, h = float(parts[3]), float(parts[4])
            except ValueError:
                continue
            if cid == person_id:
                areas.append(w * h)
        if areas:
            scored.append({
                "image": stem,
                "max_person_area": round(max(areas), 4),
                "person_count": len(areas),
            })
    scored.sort(key=lambda x: (-x["max_person_area"], -x["person_count"], x["image"]))
    return scored[:limit]


def render_person_image(delivery: Path, manifest: dict, stem: str, person_id: int) -> bytes:
    item = manifest[stem]
    img = ImageOps.exif_transpose(Image.open(delivery / item["image"])).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    lbl = delivery / item["label"]
    if lbl.is_file():
        for line in lbl.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                cid = int(float(parts[0]))
                cx, cy, bw, bh = map(float, parts[1:5])
            except ValueError:
                continue
            if cid == person_id:
                x1, y1 = (cx - bw / 2) * w, (cy - bh / 2) * h
                x2, y2 = (cx + bw / 2) * w, (cy + bh / 2) * h
                draw.rectangle([x1, y1, x2, y2], outline=(50, 240, 130), width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Day 10 Lab — Trạm Review Ảnh Nhóm VINT023</title>
<style>
  :root { --bg:#0f172a; --panel:#1e293b; --card:#263349; --text:#f1f5f9; --muted:#94a3b8; --cyan:#00e5ff; --pink:#ff2a85; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); }
  header { display:flex; flex-wrap:wrap; align-items:center; gap:12px; padding:10px 18px; background:var(--panel); border-bottom:1px solid #334155; }
  header h1 { font-size:16px; margin:0; margin-right:auto; }
  .pill { background:#334155; padding:5px 10px; border-radius:6px; font-size:13px; display:flex; align-items:center; gap:6px; }
  select, input[type=text], textarea { background:#0f172a; color:var(--text); border:1px solid #475569; border-radius:6px; padding:6px 8px; font-size:13px; }
  button { border:0; border-radius:6px; padding:8px 12px; font-weight:600; cursor:pointer; font-size:13px; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  .btn-tab { background:#334155; color:var(--text); }
  .btn-tab.active { background:#3b82f6; }
  .btn-ok { background:var(--ok); color:#052e16; }
  .btn-alt { background:#38bdf8; color:#082f49; }
  .btn-rej { background:#f87171; color:#450a0a; }
  .btn-nav { background:#475569; color:var(--text); }
  main { padding:14px 18px; max-width:1440px; margin:auto; }
  .layout { display:grid; grid-template-columns: 280px 1fr; gap:14px; }
  .sidebar { background:var(--panel); border-radius:8px; padding:10px; max-height:80vh; overflow-y:auto; }
  .cand-item { padding:8px 10px; border-radius:6px; cursor:pointer; margin-bottom:6px; border:1px solid #334155; font-size:12px; }
  .cand-item:hover { background:#334155; }
  .cand-item.active { border-color:var(--cyan); background:#172554; }
  .cand-item.done-confirmed { border-left:4px solid var(--ok); }
  .cand-item.done-rejected { border-left:4px solid var(--bad); }
  .viewer { background:var(--panel); border-radius:8px; padding:14px; }
  .banner { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px; background:var(--card); padding:10px 14px; border-radius:8px; margin-bottom:12px; }
  .vs { font-size:16px; font-weight:700; }
  .c-det { color:var(--cyan); }
  .c-pan { color:#ff6eb4; }
  .panels { display:grid; grid-template-columns: 1.2fr 1fr 1fr; gap:10px; margin-bottom:12px; }
  .panel-box { background:#0b1220; border:1px solid #334155; border-radius:8px; padding:8px; text-align:center; }
  .panel-box h3 { margin:0 0 6px 0; font-size:12px; color:var(--muted); text-transform:uppercase; }
  .panel-box img { max-width:100%; max-height:380px; border-radius:4px; object-fit:contain; }
  .controls { background:var(--card); padding:12px; border-radius:8px; display:flex; flex-direction:column; gap:10px; }
  .row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
  .h3-ok { color:var(--ok); font-size:12px; }
  .h3-bad { color:var(--warn); font-size:12px; }
  .grid-cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; }
  .mini-card { background:var(--card); border-radius:8px; padding:10px; }
  .mini-card img { width:100%; height:200px; object-fit:contain; background:#0b1220; border-radius:4px; }
  .hidden { display:none; }
</style>
</head>
<body>
<header>
  <h1>Day 10 Visual Review</h1>
  <div class="pill">Thành viên:
    <select id="shardSelect" onchange="onShardChange()"></select>
  </div>
  <div class="pill">Tên của bạn:
    <input type="text" id="reviewerName" placeholder="VD: Tung" style="width:100px">
  </div>
  <div class="pill" id="statsPill">Đang tải...</div>
  <button class="btn-tab active" id="tab1Btn" onclick="switchTab(1)">1. Review Ứng viên</button>
  <button class="btn-tab" id="tab2Btn" onclick="switchTab(2)">2. Wrong Hash &amp; Ảnh Mặt Người</button>
  <button class="btn-nav" onclick="syncState()">Đồng bộ nhóm</button>
  <button class="btn-nav" onclick="downloadShardCsv()">Tải CSV phần của mình</button>
</header>

<main>
  <section id="tab1">
    <div class="layout">
      <div class="sidebar" id="candList"></div>
      <div class="viewer" id="viewerArea">Đang tải ứng viên...</div>
    </div>
  </section>

  <section id="tab2" class="hidden">
    <div class="viewer" style="margin-bottom:16px">
      <h2>Kiểm tra ảnh <code>wrong_hash</code> (Pha 4 — mở ảnh kiểm nguyên vẹn trước khi giữ lại v2)</h2>
      <div id="hashGrid" class="grid-cards"></div>
    </div>
    <div class="viewer">
      <h2>Gợi ý ảnh có <code>person</code> lớn nhất (Pha 6 — tìm 1 ảnh thấy rõ mặt người cho <code>security.md</code>)</h2>
      <div id="faceGrid" class="grid-cards"></div>
    </div>
  </section>
</main>

<script>
let DATA = null;
let SHARD_INDEX = [];
let CUR = 0;

async function init() {
  const res = await fetch('/api/state');
  DATA = await res.json();
  const sel = document.getElementById('shardSelect');
  sel.innerHTML = '<option value="all">Tất cả (' + DATA.candidates.length + ')</option>';
  for (let i = 0; i < DATA.members; i++) {
    sel.innerHTML += '<option value="' + i + '">TV ' + (i + 1) + '</option>';
  }
  const savedName = localStorage.getItem('d10_reviewer') || '';
  document.getElementById('reviewerName').value = savedName;
  document.getElementById('reviewerName').addEventListener('input', e => {
    localStorage.setItem('d10_reviewer', e.target.value);
  });
  buildShard();
  renderTab2();
}

function buildShard() {
  const val = document.getElementById('shardSelect').value;
  const uniqImgs = [...new Set(DATA.candidates.map(c => c.image))];
  let allowedImgs = new Set(uniqImgs);
  if (val !== 'all') {
    const idx = parseInt(val, 10);
    allowedImgs = new Set(uniqImgs.filter((_, i) => i % DATA.members === idx));
  }
  SHARD_INDEX = [];
  DATA.candidates.forEach((c, i) => {
    if (allowedImgs.has(c.image)) SHARD_INDEX.push(i);
  });
  CUR = 0;
  // Jump to first unreviewed in shard
  for (let k = 0; k < SHARD_INDEX.length; k++) {
    const c = DATA.candidates[SHARD_INDEX[k]];
    if (!findReview(c)) { CUR = k; break; }
  }
  renderSidebar();
  renderCurrent();
  updateStats();
}

function onShardChange() { buildShard(); }

function switchTab(n) {
  document.getElementById('tab1').classList.toggle('hidden', n !== 1);
  document.getElementById('tab2').classList.toggle('hidden', n !== 2);
  document.getElementById('tab1Btn').classList.toggle('active', n === 1);
  document.getElementById('tab2Btn').classList.toggle('active', n === 2);
}

function findReview(c) {
  return DATA.reviews.find(r => r.image === c.image && c.possible_types.includes(r.type));
}

function updateStats() {
  const doneInShard = SHARD_INDEX.filter(i => !!findReview(DATA.candidates[i])).length;
  const totalDone = DATA.reviews.length;
  document.getElementById('statsPill').textContent =
    `Phần này: ${doneInShard}/${SHARD_INDEX.length} | Đã ghi review_log: ${totalDone} dòng`;
}

function renderSidebar() {
  const box = document.getElementById('candList');
  box.innerHTML = SHARD_INDEX.map((ci, k) => {
    const c = DATA.candidates[ci];
    const rev = findReview(c);
    const cls = ['cand-item', k === CUR ? 'active' : '', rev ? 'done-' + rev.verdict : ''].join(' ');
    const badge = rev ? `[${rev.verdict === 'confirmed' ? 'OK' : 'REJ'}: ${rev.type}]` : `[chờ xem]`;
    return `<div class="${cls}" onclick="CUR=${k};renderSidebar();renderCurrent()">
      <div><b>#${ci+1} ${c.image}</b></div>
      <div style="color:#94a3b8">${c.suggested_type} ${badge}</div>
    </div>`;
  }).join('');
}

function renderCurrent() {
  const area = document.getElementById('viewerArea');
  if (!SHARD_INDEX.length) { area.innerHTML = 'Không có ứng viên trong phần này.'; return; }
  const ci = SHARD_INDEX[CUR];
  const c = DATA.candidates[ci];
  const rev = findReview(c);
  const swap = c.suggested_type === 'class_swap_or_category_swap';
  const metricTxt = Object.entries(c.metrics || {}).map(([k,v]) => `${k}=${v}`).join(' · ');
  const existingNote = rev ? rev.note : '';

  let actionBtns = '';
  if (swap) {
    actionBtns = `
      <button id="b1" class="btn-ok" onclick="submitDecision('class_swap','confirmed')">Confirm: class_swap (DET '${c.det_class}' sai)</button>
      <button id="b2" class="btn-alt" onclick="submitDecision('category_swap','confirmed')">Confirm: category_swap (PAN '${c.pan_class}' sai)</button>
      <button id="b3" class="btn-rej" onclick="submitDecision('class_swap','rejected')">Reject (lệch tự nhiên / khác vật)</button>
    `;
  } else {
    actionBtns = `
      <button id="b1" class="btn-ok" onclick="submitDecision('${c.suggested_type}','confirmed')">Confirm: ${c.suggested_type}</button>
      <button id="b3" class="btn-rej" onclick="submitDecision('${c.suggested_type}','rejected')">Reject (nhiễu COCO / hợp lệ)</button>
    `;
  }

  const starterHint = swap
    ? `mở ảnh: thấy [VẬT THẬT], nên [DET hay PAN] sai`
    : `mở ảnh: [MÔ TẢ VẬT & VỊ TRÍ BOX SO VỚI ẢNH THẬT]`;

  area.innerHTML = `
    <div class="banner">
      <div>
        <div class="vs">Ảnh <code>${c.image}</code> (${CUR+1}/${SHARD_INDEX.length}) —
          <span class="c-det">DET: ${c.det_class || '—'}</span> vs <span class="c-pan">PAN: ${c.pan_class || '—'}</span>
        </div>
        <div style="font-size:12px;color:#94a3b8;margin-top:4px">${c.reason} | ${metricTxt}</div>
      </div>
      <div class="row">
        <button class="btn-nav" onclick="go(-1)" ${CUR===0?'disabled':''}>&larr; Trước</button>
        <button class="btn-nav" onclick="go(1)" ${CUR===SHARD_INDEX.length-1?'disabled':''}>Sau &rarr;</button>
      </div>
    </div>

    <div class="panels">
      <div class="panel-box">
        <h3>1. Toàn ảnh + Overlay (Cyan=DET, Hồng=PAN)</h3>
        <img src="/api/img?idx=${ci}&mode=full">
      </div>
      <div class="panel-box">
        <h3>2. Zoom GỐC (Không vẽ che vật)</h3>
        <img src="/api/img?idx=${ci}&mode=crop_raw">
      </div>
      <div class="panel-box">
        <h3>3. Zoom + Overlay (So biên box &amp; mask)</h3>
        <img src="/api/img?idx=${ci}&mode=crop_overlay">
      </div>
    </div>

    <div class="controls">
      <div class="row" style="justify-content:space-between">
        <label for="noteInput"><b>Ghi chú mắt người (bắt buộc &ge; 20 ký tự, nêu rõ thấy gì trong ảnh):</b></label>
        <span id="noteStatus" class="h3-bad"></span>
      </div>
      <textarea id="noteInput" rows="2" placeholder="Ví dụ: ${starterHint}" oninput="checkNote()">${existingNote}</textarea>
      <div class="row">
        ${actionBtns}
        <span style="margin-left:auto;font-size:12px;color:#94a3b8">
          Loại tuỳ chỉnh:
          <select id="overrideType">
            <option value="">-- Giữ mặc định --</option>
            <option value="class_swap">class_swap</option>
            <option value="category_swap">category_swap</option>
            <option value="bbox_drift">bbox_drift</option>
            <option value="missing_box">missing_box</option>
            <option value="instance_merge">instance_merge</option>
          </select>
        </span>
      </div>
    </div>
  `;
  checkNote();
}

function stripPrefix(note) {
  return note.replace(/^\[[^\]]+\]\s*/, '').trim();
}

function checkNote() {
  const ci = SHARD_INDEX[CUR];
  const c = DATA.candidates[ci];
  const raw = stripPrefix(document.getElementById('noteInput').value.trim());
  const val = buildFullNote(raw);
  const status = document.getElementById('noteStatus');
  const sameSlot = r => r.image === c.image && c.possible_types.includes(r.type);
  const dup = DATA.reviews.some(r => !sameSlot(r) && (r.note === val || stripPrefix(r.note) === raw));
  const ok = raw.length >= 20 && !dup && !val.includes('<<') && !val.includes('[MÔ TẢ');
  if (raw.length < 20) {
    status.textContent = `Còn thiếu ${20 - raw.length} ký tự mô tả thực (chưa tính [Tên]: ${raw.length}/20)`;
    status.className = 'h3-bad';
  } else if (dup) {
    status.textContent = `Trùng y hệt ghi chú của ảnh/ứng viên khác (vi phạm H3)! Hãy viết cụ thể hơn.`;
    status.className = 'h3-bad';
  } else {
    status.textContent = `Đạt chuẩn H3 (${raw.length} ký tự mô tả, không trùng)`;
    status.className = 'h3-ok';
  }
  ['b1','b2','b3'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = !ok;
  });
}

function buildFullNote(raw) {
  const revName = document.getElementById('reviewerName').value.trim();
  const clean = stripPrefix(raw);
  if (!clean) return '';
  if (revName) return `[${revName}] ${clean}`;
  return clean;
}

async function syncState() {
  const res = await fetch('/api/state');
  const fresh = await res.json();
  DATA.reviews = fresh.reviews;
  renderSidebar();
  renderCurrent();
  updateStats();
}

async function submitDecision(type, verdict) {
  const ci = SHARD_INDEX[CUR];
  const c = DATA.candidates[ci];
  const override = document.getElementById('overrideType').value;
  const finalType = override || type;
  const note = buildFullNote(document.getElementById('noteInput').value.trim());
  const res = await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ image: c.image, type: finalType, verdict, note })
  });
  const out = await res.json();
  if (!res.ok) { alert(out.error || 'Lỗi lưu'); return; }
  DATA.reviews = out.reviews;
  updateStats();
  if (CUR < SHARD_INDEX.length - 1) CUR++;
  renderSidebar();
  renderCurrent();
}

function go(delta) {
  CUR = Math.max(0, Math.min(SHARD_INDEX.length - 1, CUR + delta));
  renderSidebar();
  renderCurrent();
}

function downloadShardCsv() {
  const shardImgs = new Set(SHARD_INDEX.map(i => DATA.candidates[i].image));
  const rows = DATA.reviews.filter(r => shardImgs.has(r.image));
  const esc = s => '"' + String(s).replace(/"/g, '""') + '"';
  const lines = ['image,type,verdict,note', ...rows.map(r => [r.image, r.type, r.verdict, esc(r.note)].join(','))];
  const blob = new Blob([lines.join('\n') + '\n'], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const v = document.getElementById('shardSelect').value;
  a.download = `review_log_${v === 'all' ? 'all' : 'tv' + (parseInt(v,10)+1)}.csv`;
  a.click();
}

function renderTab2() {
  const hg = document.getElementById('hashGrid');
  if (!DATA.wrong_hash.length) {
    hg.innerHTML = '<div style="color:#94a3b8">Không có ảnh wrong_hash (hoặc chưa truyền --rules).</div>';
  } else {
    hg.innerHTML = DATA.wrong_hash.map(h => `
      <div class="mini-card">
        <img src="/api/person_img?image=${h.image}">
        <div style="margin-top:6px"><b>${h.image}</b></div>
        <div style="font-size:12px;color:${h.status==='intact'?'#22c55e':'#ef4444'}">
          Trạng thái: ${h.status} (${h.dims}, ${h.size_kb} KB)
        </div>
      </div>
    `).join('');
  }
  const fg = document.getElementById('faceGrid');
  fg.innerHTML = DATA.person_images.map(p => `
    <div class="mini-card">
      <img src="/api/person_img?image=${p.image}">
      <div style="margin-top:6px"><code>${p.image}</code></div>
      <div style="font-size:12px;color:#94a3b8">max person area: ${p.max_person_area} (${p.person_count} người)</div>
    </div>
  `).join('');
}

init();
</script>
</body>
</html>
"""


class ReviewState:
    def __init__(self, delivery: Path, candidates_path: Path, out_csv: Path, rules_path: Path | None, members: int):
        self.delivery = delivery
        self.manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))["items"]
        self.classes = load_classes(delivery)
        self.person_id = self.classes.index("person") if "person" in self.classes else -1
        self.candidates = json.loads(candidates_path.read_text(encoding="utf-8")).get("candidates", [])
        self.out_csv = out_csv
        self.members = members
        self.wrong_hash = check_wrong_hash_images(delivery, self.manifest, rules_path)
        self.person_images = find_person_candidates(delivery, self.manifest, self.classes)
        self.lock = threading.Lock()
        self.reviews = self._load_reviews()

    def _load_reviews(self) -> list[dict[str, str]]:
        if not self.out_csv.is_file():
            return []
        with self.out_csv.open(encoding="utf-8-sig", newline="") as f:
            return [
                {
                    "image": (r.get("image") or "").strip(),
                    "type": (r.get("type") or "").strip(),
                    "verdict": (r.get("verdict") or "").strip(),
                    "note": (r.get("note") or "").strip(),
                }
                for r in csv.DictReader(f)
                if (r.get("image") or "").strip()
            ]

    @staticmethod
    def strip_prefix(note: str) -> str:
        return re.sub(r"^\[[^\]]+\]\s*", "", note.strip()).strip()

    def save_review(self, image: str, rtype: str, verdict: str, note: str) -> list[dict[str, str]]:
        if verdict not in ("confirmed", "rejected"):
            raise ValueError("verdict phải là confirmed hoặc rejected")
        if verdict == "confirmed" and rtype not in metrics.SEMANTIC_TYPES:
            raise ValueError(f"type '{rtype}' không hợp lệ cho confirmed")
        raw_obs = self.strip_prefix(note)
        if len(raw_obs) < 20:
            raise ValueError("Mô tả thực trong ghi chú (chưa tính [Tên]) phải >= 20 ký tự")

        with self.lock:
            swap_pair = {"class_swap", "category_swap"}
            def is_same_slot(r: dict[str, str]) -> bool:
                return r["image"] == image and (r["type"] == rtype or (r["type"] in swap_pair and rtype in swap_pair))

            if any(not is_same_slot(r) and (r["note"] == note or self.strip_prefix(r["note"]) == raw_obs) for r in self.reviews):
                raise ValueError("Ghi chú trùng lặp với dòng khác (vi phạm H3)")

            self.reviews = [r for r in self.reviews if not is_same_slot(r)]
            self.reviews.append({"image": image, "type": rtype, "verdict": verdict, "note": note})
            self.reviews.sort(key=lambda r: (r["image"], r["type"]))
            self.out_csv.parent.mkdir(parents=True, exist_ok=True)
            with self.out_csv.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["image", "type", "verdict", "note"])
                w.writeheader()
                w.writerows(self.reviews)
            return list(self.reviews)

    @lru_cache(maxsize=256)
    def render_cand(self, idx: int, mode: str) -> bytes:
        return render_candidate_panel(self.delivery, self.manifest, self.candidates[idx], mode)

    @lru_cache(maxsize=64)
    def render_person(self, stem: str) -> bytes:
        return render_person_image(self.delivery, self.manifest, stem, self.person_id)


def make_handler(state: ReviewState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send_json(self, status: int, payload: dict) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/":
                raw = HTML_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if parsed.path == "/api/state":
                self._send_json(200, {
                    "candidates": state.candidates,
                    "reviews": state.reviews,
                    "members": state.members,
                    "wrong_hash": state.wrong_hash,
                    "person_images": state.person_images,
                })
                return
            if parsed.path == "/api/img":
                idx = int(qs["idx"][0])
                mode = qs.get("mode", ["full"])[0]
                png = state.render_cand(idx, mode)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if parsed.path == "/api/person_img":
                stem = qs["image"][0]
                png = state.render_person(stem)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/api/save":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            try:
                reviews = state.save_review(
                    body["image"].strip(),
                    body["type"].strip(),
                    body["verdict"].strip(),
                    body["note"].strip(),
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, {"reviews": reviews})

    return Handler


def detect_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> int:
    ap = argparse.ArgumentParser(description="Web UI xem ảnh đối chiếu cho nhóm 5 người")
    ap.add_argument("--delivery", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", required=True, help="File review_log.csv để lưu kết quả")
    ap.add_argument("--rules", help="File rules.json (tuỳ chọn, để kiểm wrong_hash ở Tab 2)")
    ap.add_argument("--members", type=int, default=5)
    ap.add_argument("--host", default="127.0.0.1", help="Mặc định 127.0.0.1; truyền 0.0.0.0 để 5 máy cùng vào qua LAN")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    state = ReviewState(
        Path(args.delivery),
        Path(args.candidates),
        Path(args.out),
        Path(args.rules) if args.rules else None,
        args.members,
    )
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    local_url = f"http://127.0.0.1:{args.port}/"
    print(f"Đang mở Trạm Review Ảnh tại {local_url} (Ctrl+C để dừng)...", flush=True)
    if args.host == "0.0.0.0":
        lan_ip = detect_lan_ip()
        print(f"Link LAN cho các thành viên khác (cùng WiFi): http://{lan_ip}:{args.port}/", flush=True)
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(local_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã lưu và dừng server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
