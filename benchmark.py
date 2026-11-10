# -*- coding: utf-8 -*-
"""Đo tốc độ với DB cỡ thật của đề (34 tỉnh, ~3.300 phường/xã, ~34x10x70 = 23.800 đường).

DB thật chưa có nên tên đường/phường được sinh ngẫu nhiên từ các âm tiết tiếng Việt,
cộng thêm toàn bộ DB mẫu trong data/ để các test case vẫn chạy được.

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

FAMILY = ("Nguyễn Trần Lê Phạm Hoàng Huỳnh Phan Vũ Võ Đặng Bùi Đỗ Hồ Ngô Dương Lý "
          "Đinh Mai Trịnh Lương Tạ Cao Châu Hà Kiều").split()
SYLLABLES = ("An Bình Cường Dũng Hải Hùng Khoa Long Minh Nam Phong Quân Sơn Tâm Thành Trí "
             "Tuấn Vinh Yên Lộc Phúc Thịnh Hòa Hưng Xuân Thu Đông Mỹ Lợi Tân Phú Quý Đức "
             "Hiệp Thuận Nghĩa Trung Hiếu Lâm Sang Kiên Định Toàn Thắng Bảo Châu Ngọc Hồng "
             "Lan Mai Đào Cúc Trúc Liên Hoa Tiến Đạt Khánh Hạnh Nhân Tín Quang Văn Kim "
             "Thạch Thủy Giang Hiền Lạc Thái Uyên Vân Tường Khải Hào Kỳ Tú Duy").split()


def _read(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _unique_names(rng, count, make):
    names = set()
    while len(names) < count:
        names.add(make())
    return sorted(names)


def make_big_db(folder, n_streets=23800, n_wards=3300, seed=2025):
    """Ghi 3 file DB vào `folder`, trả về dict tham số cho Solution(...)."""
    rng = random.Random(seed)

    def street():
        if rng.random() < 0.6:
            return " ".join([rng.choice(FAMILY)] + rng.sample(SYLLABLES, rng.choice((1, 2, 2, 3))))
        return " ".join(rng.sample(SYLLABLES, rng.choice((2, 2, 3))))

    def ward():
        kind = rng.choice(("Phường", "Phường", "Xã"))
        return kind + " " + " ".join(rng.sample(SYLLABLES, rng.choice((2, 2, 3))))

    streets = _read("list_street.txt") + _unique_names(rng, n_streets, street)
    wards = _read("list_ward.txt") + _unique_names(rng, n_wards, ward)
    provinces = _read("list_province.txt")
    paths = {}
    for key, items in (("street_path", streets), ("ward_path", wards), ("province_path", provinces)):
        paths[key] = os.path.join(folder, key.replace("_path", "") + ".txt")
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
    """Sinh địa chỉ có nhiễu (bỏ dấu, viết tắt, lỗi chính tả, thiếu dấu phẩy) kèm đáp án."""
    rng = random.Random(seed)
    lists = []
    for key in ("street_path", "ward_path", "province_path"):
        with open(paths[key], encoding="utf-8") as f:
            lists.append([line.strip() for line in f if line.strip()])
    samples = []
    for _ in range(count):
        street, ward, province = (rng.choice(items) for items in lists)
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
        for name, samples in (("test_cases.json", cases), ("2000 mẫu nhiễu ngẫu nhiên", noisy)):
            correct, total, worst, avg = _run(solver, samples)
            print("%-26s %8d %6d %9.2f %13.4f %13.4f" % (name, correct, total, 10.0 * correct / total,
                                                        worst, avg))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
