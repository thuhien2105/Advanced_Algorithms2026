# -*- coding: utf-8 -*-
"""Đo tốc độ và độ chính xác với DB địa chỉ THẬT, đúng cấu trúc đề (slide 7):
34 tỉnh/thành, mỗi tỉnh 10 phường/xã, mỗi phường ~70 tên đường.

DB thật nằm trong data_real/ (dựng bằng tools/build_real_db.py từ danh mục hành chính 2025
và OpenStreetMap). Benchmark gộp thêm DB mẫu trong data/ để các test case vẫn chạy được.
Địa chỉ thử là bộ ba ĐÚNG (tên đường nằm trong phường, phường thuộc tỉnh) rồi thêm nhiễu.

    python benchmark.py
"""
import json
import os
import random
import shutil
import sys
import tempfile
import time
import unicodedata

from solution import Solution

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
REAL = os.path.join(ROOT, "data_real")


def _read(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8-sig") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


NO_REAL_DATA = "Chưa có data_real/. Chạy: python tools/build_real_db.py (cần internet, 1 lần)"


def has_real_data():
    return os.path.exists(os.path.join(REAL, "addresses.json"))


def load_addresses():
    """[{"province", "ward", "streets": [...]}] – các bộ (tỉnh, phường, đường) có thật."""
    path = os.path.join(REAL, "addresses.json")
    if not os.path.exists(path):
        raise SystemExit(NO_REAL_DATA)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_big_db(folder):
    """Ghi 3 file DB (data_real/ + data/) vào `folder`, trả về dict tham số cho Solution(...)."""
    load_addresses()
    paths = {}
    for key, fname in (("street_path", "list_street.txt"), ("ward_path", "list_ward.txt"),
                       ("province_path", "list_province.txt")):
        items = list(dict.fromkeys(_read(REAL, fname) + _read(DATA, fname)))
        paths[key] = os.path.join(folder, fname)
        with open(paths[key], "w", encoding="utf-8") as f:
            f.write("\n".join(items) + "\n")
    return paths


def _strip_accents(text):
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _typo(rng, text):
    """Xoá / lặp / đổi một ký tự trong một từ dài >= 5 (mô phỏng lỗi OCR)."""
    words = text.split(" ")
    long_words = [i for i, w in enumerate(words) if len(w) >= 5]
    if not long_words:
        return text
    i = rng.choice(long_words)
    w = words[i]
    p = rng.randrange(1, len(w))
    op = rng.choice(("del", "dup", "sub"))
    if op == "del":
        w = w[:p] + w[p + 1:]
    elif op == "dup":
        w = w[:p] + w[p] + w[p:]
    else:
        w = w[:p] + rng.choice("aeiounhgtc") + w[p + 1:]
    words[i] = w
    return " ".join(words)


def make_noisy_samples(paths, count, seed=7):
    """Sinh địa chỉ THẬT có nhiễu (bỏ dấu, viết tắt, lỗi chính tả, thiếu dấu phẩy) kèm đáp án.
    `paths` giữ để tương thích; dữ liệu lấy từ data_real/addresses.json."""
    rng = random.Random(seed)
    rows = load_addresses()
    samples = []
    for _ in range(count):
        row = rng.choice(rows)
        street, ward, province = rng.choice(row["streets"]), row["ward"], row["province"]
        if rng.random() < 0.15:
            street = ""
        s_txt = street
        w_txt = ward.replace("Phường ", rng.choice(("Phường ", "P. ", "P.", "phuong "))) \
                    .replace("Xã ", rng.choice(("Xã ", "X. ", "xa ")))
        p_txt = province.replace("Thành phố ", rng.choice(("Thành phố ", "TP. ", "TP ", "Tp.", ""))) \
                        .replace("Tỉnh ", rng.choice(("Tỉnh ", "T. ", "")))
        if rng.random() < 0.3 and s_txt:
            s_txt = _typo(rng, s_txt)
        if rng.random() < 0.2:
            w_txt = _typo(rng, w_txt)
        parts = [str(rng.randint(1, 500)) + " " + s_txt] if s_txt else []
        parts += [w_txt, p_txt]
        address = rng.choice((", ", " ", ",")).join(parts)
        if rng.random() < 0.3:
            address = _strip_accents(address)
        samples.append((address, {"street": street, "ward": ward, "province": province}))
    return samples


def _run(solver, samples):
    correct, times = 0, []
    for address, expected in samples:
        t0 = time.perf_counter()
        out = solver.process(address)
        times.append(time.perf_counter() - t0)
        correct += sum(out[k] == expected[k] for k in expected)
    total = 3 * len(samples)
    return correct, total, max(times), sum(times) / len(times)


def use_utf8_stdout():
    """Console Windows mặc định cp1252 -> in tiếng Việt bị lỗi."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def main():
    use_utf8_stdout()
    folder = tempfile.mkdtemp()
    try:
        paths = make_big_db(folder)
        t0 = time.perf_counter()
        solver = Solution(**paths)
        print("Khởi tạo (đọc DB + dựng Trie): %.2f s, %d tên" % (time.perf_counter() - t0, len(solver.names)))

        with open(os.path.join(ROOT, "tests", "test_cases.json"), encoding="utf-8") as f:
            cases = [(c["address"], c["result"]) for c in json.load(f)]
        noisy = make_noisy_samples(paths, 2000)

        print("%-26s %8s %6s %9s %13s %13s" % ("bộ dữ liệu", "correct", "total", "score/10",
                                                "max_time_sec", "avg_time_sec"))
        for name, samples in (("test_cases.json", cases), ("2000 địa chỉ thật có nhiễu", noisy)):
            correct, total, worst, avg = _run(solver, samples)
            print("%-26s %8d %6d %9.2f %13.4f %13.4f" % (name, correct, total, 10.0 * correct / total,
                                                        worst, avg))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
