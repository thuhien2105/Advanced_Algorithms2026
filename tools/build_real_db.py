# -*- coding: utf-8 -*-
"""Dựng DB địa chỉ THẬT theo đúng cấu trúc đề (slide 7):
34 tỉnh/thành, mỗi tỉnh chọn ngẫu nhiên 10 phường/xã, mỗi phường ~70 tên đường.

Nguồn (cần internet, chỉ khi DỰNG DB; lời giải vẫn chạy offline):
  - Tỉnh, phường/xã sau sắp xếp 2025: https://provinces.open-api.vn/api/v2/
  - Tên đường nằm trong ranh giới từng phường: OpenStreetMap qua Overpass API
    (dữ liệu © OpenStreetMap contributors, giấy phép ODbL).

    python tools/build_real_db.py                 # ghi vào data_real/
    python tools/build_real_db.py --out data_real --seed 2025

Kết quả (mỗi file một tên mỗi dòng, cùng định dạng data/):
  data_real/list_province.txt, list_ward.txt, list_street.txt
  data_real/addresses.json   [{"province", "ward", "streets": [...]}] để sinh địa chỉ ĐÚNG
                             (đường thuộc phường, phường thuộc tỉnh)
Mọi response được cache trong tools/.cache/ nên chạy lại / chạy tiếp khi bị ngắt không phải tải lại.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", ".cache")
API = "https://provinces.open-api.vn/api/v2"
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "address-segmentation-dataset/1.0"}

WARDS_PER_PROVINCE = 10
STREETS_PER_WARD = 70
MIN_STREETS = 15          # phường có ít hơn số tên đường này trên OSM thì chọn phường khác

# Không phải tên đường: hẻm / ngõ / cầu / hầm / nút giao...
SKIP = re.compile(r"^(hẻm|hem|ngõ|ngách|kiệt|kiet|cầu|hầm|dẫn|nút|vòng xoay|bùng binh|lối|"
                  r"đường dẫn|đường nội bộ|nội bộ|cao tốc|đường cao tốc|bến|phà|công trường)\b", re.I)


def _get(url, data=None, tries=8):
    key = hashlib.sha1((url + "|" + (data or "")).encode()).hexdigest()
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    body = urllib.parse.urlencode({"data": data}).encode() if data else None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=UA)
            result = json.load(urllib.request.urlopen(req, timeout=200))
            os.makedirs(CACHE, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
            if url == OVERPASS:
                time.sleep(1)   # lịch sự với máy chủ Overpass dùng chung
            return result
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            wait = min(120, 5 * 2 ** k)
            print(f"    lỗi {e!r}, thử lại sau {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("không tải được " + url)


def _core(name):
    """'Thành phố Đồng Nai' / 'Tỉnh Đồng Nai' -> 'Đồng Nai' (OSM có thể chưa đổi tên tỉnh)."""
    return re.sub(r"^(Thành phố|Tỉnh)\s+", "", name).strip()


def clean_street(name):
    name = re.sub(r"\s+", " ", name).strip()
    if not name or SKIP.match(name) or "(" in name or len(name) > 40:
        return None
    if not re.search(r"[A-Za-zÀ-ỹĐđ]{2}", name):
        return None   # không có từ nào >= 2 chữ cái ("H3", "D1") -> mã đường, bỏ
    m = re.match(r"^Đường\s+(.+)$", name)
    if m and not re.match(r"^(số\b|\d)", m.group(1), re.I):
        name = m.group(1)   # "Đường Yersin" -> "Yersin"; giữ "Đường số 5", "Đường 3/2"
    return name


def osm_ward_names(province_core):
    q = (f'[out:json][timeout:180];area["boundary"="administrative"]["admin_level"="4"]'
         f'["name"~"{province_core}$"]->.p;rel(area.p)["boundary"="administrative"]["name"];out tags;')
    return {e["tags"]["name"] for e in _get(OVERPASS, q)["elements"]}


def osm_streets(province_core, ward):
    q = (f'[out:json][timeout:180];area["boundary"="administrative"]["admin_level"="4"]'
         f'["name"~"{province_core}$"]->.p;'
         f'rel(area.p)["boundary"="administrative"]["name"="{ward}"];map_to_area->.a;'
         f'way(area.a)["highway"]["name"];out tags;')
    names = set()
    for e in _get(OVERPASS, q)["elements"]:
        n = clean_street(e["tags"]["name"])
        if n:
            names.add(n)
    return sorted(names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data_real"))
    ap.add_argument("--seed", type=int, default=2025)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    provinces = _get(API + "/p/")
    print(f"{len(provinces)} tỉnh/thành")
    rows = []
    for p in provinces:
        detail = _get(f"{API}/p/{p['code']}?depth=2")
        core = _core(p["name"])
        in_osm = osm_ward_names(core)
        candidates = [w["name"] for w in detail["wards"] if w["name"] in in_osm]
        rng.shuffle(candidates)
        picked = []
        for ward in candidates:
            if len(picked) == WARDS_PER_PROVINCE:
                break
            streets = osm_streets(core, ward)
            if len(streets) < MIN_STREETS:
                continue
            rng.shuffle(streets)
            picked.append({"province": p["name"], "ward": ward, "streets": sorted(streets[:STREETS_PER_WARD])})
        n_st = sum(len(x["streets"]) for x in picked)
        print(f"  {p['name']:28s} {len(detail['wards']):4d} phường/xã, {len(in_osm & {w['name'] for w in detail['wards']}):4d} có trên OSM"
              f" -> chọn {len(picked)}, {n_st} tên đường")
        rows.extend(picked)

    os.makedirs(args.out, exist_ok=True)
    streets = sorted({s for r in rows for s in r["streets"]})
    wards = sorted({r["ward"] for r in rows})
    for fname, items in (("list_province.txt", [p["name"] for p in provinces]),
                         ("list_ward.txt", wards), ("list_street.txt", streets)):
        with open(os.path.join(args.out, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(items) + "\n")
    with open(os.path.join(args.out, "addresses.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"xong: {len(provinces)} tỉnh, {len(wards)} phường/xã, {len(streets)} tên đường (không trùng) -> {args.out}")


if __name__ == "__main__":
    main()
