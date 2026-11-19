#!/usr/bin/env python3
"""Tải nhanh chỉ các file val2017 từ ZIP COCO chính thức qua HTTP Range (~41 MB thay vì 1.1 GB).

Tạo đúng 2 file cache hợp lệ trong data_source/cache/ với kiểm tra CRC-32 từng byte,
sau đó chạy lại nguyên bản `python3 scripts/download_public.py` (không sửa scripts/).
"""

from __future__ import annotations

import argparse
import struct
import time
import urllib.request
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    (
        "http://images.cocodataset.org/annotations/annotations_trainval2017.zip",
        "annotations_trainval2017.zip",
        ["annotations/instances_val2017.json"],
    ),
    (
        "http://images.cocodataset.org/annotations/panoptic_annotations_trainval2017.zip",
        "panoptic_annotations_trainval2017.zip",
        ["annotations/panoptic_val2017.json", "annotations/panoptic_val2017.zip"],
    ),
]


def http_range(url: str, start: int, end: int, retries: int = 6) -> bytes:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"Range": f"bytes={start}-{end}", "User-Agent": "day10-lab"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status not in (200, 206):
                    raise OSError(f"HTTP {resp.status}")
                data = resp.read()
                expected = end - start + 1
                if len(data) != expected:
                    raise OSError(f"Short range read: got {len(data)} != {expected}")
                return data
        except Exception as exc:
            if attempt == retries - 1:
                raise
            wait = min(10, 2 * (attempt + 1))
            print(f"  [retry {attempt + 1}/{retries}] {exc} -> ngủ {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError("Unreachable")


def fetch_zip_entries(url: str) -> tuple[int, dict[str, dict]]:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "day10-lab"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.headers.get("Accept-Ranges", "").lower() != "bytes":
            raise SystemExit(f"Server không hỗ trợ HTTP Range cho {url}")
        total_size = int(resp.headers["Content-Length"])

    tail_start = max(0, total_size - 65536)
    tail = http_range(url, tail_start, total_size - 1)
    eocd = tail.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise SystemExit(f"Không thấy EOCD trong {url}")
    cd_size, cd_offset = struct.unpack("<II", tail[eocd + 12 : eocd + 20])
    cd_data = http_range(url, cd_offset, cd_offset + cd_size - 1)

    entries: dict[str, dict] = {}
    pos = 0
    while pos < len(cd_data):
        if cd_data[pos : pos + 4] != b"PK\x01\x02":
            raise SystemExit("Central directory bị lỗi chữ ký")
        comp_method = struct.unpack("<H", cd_data[pos + 10 : pos + 12])[0]
        crc, comp_size, uncomp_size, fn_len, ex_len, cm_len = struct.unpack("<IIIHHH", cd_data[pos + 16 : pos + 34])
        lhf_off = struct.unpack("<I", cd_data[pos + 42 : pos + 46])[0]
        name = cd_data[pos + 46 : pos + 46 + fn_len].decode("utf-8", "replace")
        entries[name] = {
            "name": name,
            "method": comp_method,
            "crc": crc,
            "comp_size": comp_size,
            "uncomp_size": uncomp_size,
            "lhf_off": lhf_off,
        }
        pos += 46 + fn_len + ex_len + cm_len
    return total_size, entries


def download_entry_verified(url: str, meta: dict, chunk_bytes: int = 2 * 1024 * 1024) -> bytes:
    lhf = http_range(url, meta["lhf_off"], meta["lhf_off"] + 29)
    if lhf[:4] != b"PK\x03\x04":
        raise SystemExit(f"Local header sai ở {meta['name']}")
    fn_len, ex_len = struct.unpack("<HH", lhf[26:30])
    data_start = meta["lhf_off"] + 30 + fn_len + ex_len
    comp_size = meta["comp_size"]

    buf = bytearray()
    downloaded = 0
    while downloaded < comp_size:
        end = min(comp_size, downloaded + chunk_bytes) - 1
        part = http_range(url, data_start + downloaded, data_start + end)
        buf += part
        downloaded += len(part)
        pct = downloaded * 100.0 / comp_size
        print(f"    {meta['name']}: {downloaded / 1048576:.1f}/{comp_size / 1048576:.1f} MB ({pct:.0f}%)", flush=True)

    if meta["method"] == 8:
        raw = zlib.decompress(bytes(buf), -15)
    elif meta["method"] == 0:
        raw = bytes(buf)
    else:
        raise SystemExit(f"Unsupported compression method {meta['method']} for {meta['name']}")

    actual_crc = zlib.crc32(raw) & 0xFFFFFFFF
    if len(raw) != meta["uncomp_size"] or actual_crc != meta["crc"]:
        raise SystemExit(
            f"CRC/size mismatch cho {meta['name']}: len {len(raw)} vs {meta['uncomp_size']}, crc {actual_crc:08x} vs {meta['crc']:08x}"
        )
    return raw


def build_cache_zip(url: str, dest: Path, wanted_names: list[str]) -> None:
    if dest.is_file() and dest.stat().st_size > 0:
        with zipfile.ZipFile(dest) as zf:
            names = set(zf.namelist())
            if all(w in names for w in wanted_names) and zf.testzip() is None:
                print(f"cached (verified) {dest}")
                return

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Inspecting {url} ...", flush=True)
    _, entries = fetch_zip_entries(url)

    partial = dest.with_suffix(".zip.part")
    if partial.exists():
        partial.unlink()

    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name in wanted_names:
            if name not in entries:
                raise SystemExit(f"Không thấy {name} trong {url}")
            raw = download_entry_verified(url, entries[name])
            compress_type = zipfile.ZIP_STORED if name.endswith(".zip") else zipfile.ZIP_DEFLATED
            zout.writestr(name, raw, compress_type=compress_type)

    with zipfile.ZipFile(partial) as zcheck:
        bad = zcheck.testzip()
        if bad is not None:
            raise SystemExit(f"Zip kiểm tra lỗi ở {bad}")
    partial.replace(dest)
    print(f"ready {dest} ({dest.stat().st_size / 1048576:.1f} MB)", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Tải nhanh phần val2017 vào data_source/cache bằng HTTP Range")
    ap.add_argument("--root", default="data_source")
    args = ap.parse_args()

    cache_dir = (ROOT / args.root if not Path(args.root).is_absolute() else Path(args.root)) / "cache"
    for url, fname, wanted in TARGETS:
        build_cache_zip(url, cache_dir / fname, wanted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
