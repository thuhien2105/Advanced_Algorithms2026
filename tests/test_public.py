# -*- coding: utf-8 -*-
"""Chạy bộ PUBLIC TEST của thầy (tests/public/: 200 mẫu + DB 3 file), chấm giống slide 10.

Chạy:  python -m unittest tests.test_public -v      (đứng ở thư mục gốc dự án)

  - TestPublic       : từng mẫu phải đúng cả 3 trường, đo max/avg time theo giới hạn slide 11.
  - TestPublicNhieu  : làm nhiễu chính 200 mẫu (bỏ dấu, bỏ dấu phẩy, viết tắt, gõ sai 1 ký tự...)
                       để xem code chịu lỗi tới đâu; chỉ yêu cầu điểm >= MIN_NOISY_SCORE vì có ca
                       mơ hồ thật (DB có cả "Trần Hưng Đạo" lẫn "Trấn Hưng Đạo", bỏ dấu là trùng).
"""
import json
import os
import random
import sys
import time
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from solution import FIELDS, Solution  # noqa: E402

PUBLIC = os.path.join(ROOT, "tests", "public")
MAX_TIME = 0.1          # slide 11
AVG_TIME = 0.01
MIN_NOISY_SCORE = 9.5   # điểm /10 tối thiểu cho mỗi kiểu nhiễu


def _load_solver():
    return Solution(province_path=os.path.join(PUBLIC, "list_province.txt"),
                    ward_path=os.path.join(PUBLIC, "list_ward.txt"),
                    street_path=os.path.join(PUBLIC, "list_street.txt"))


def _load_cases():
    with open(os.path.join(PUBLIC, "public.json"), encoding="utf-8") as f:
        return json.load(f)


def _run(solver, samples):
    """samples: [(address, result)] -> (correct, total, max_time, avg_time, các trường sai)."""
    solver.process(samples[0][0])  # làm nóng
    correct, times, wrong = 0, [], []
    for address, expected in samples:
        t0 = time.perf_counter()
        out = solver.process(address)
        times.append(time.perf_counter() - t0)
        for field in FIELDS:
            if out[field] == expected[field]:
                correct += 1
            else:
                wrong.append((address, field, out[field], expected[field]))
    return correct, 3 * len(samples), max(times), sum(times) / len(times), wrong


def _report(title, rows):
    # in bằng chữ không dấu để console nào cũng đọc được
    lines = ["", title, "  %-24s %8s %6s %9s %13s %13s" % ("name", "correct", "total", "score/10",
                                                           "max_time_sec", "avg_time_sec")]
    lines += ["  %-24s %8d %6d %9.2f %13.4f %13.4f" % row for row in rows]
    sys.stderr.write("\n".join(lines) + "\n\n")


# ------------------------------------------------------------------ các kiểu nhiễu
def _strip_accents(text):
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _typo(rng, text):
    """Xoá / sửa / lặp 1 ký tự (không phải ký tự đầu) trong một từ dài >= 5."""
    words = text.split(" ")
    idx = [i for i, w in enumerate(words) if len(w) >= 5]
    if not idx:
        return text
    i = rng.choice(idx)
    w = words[i]
    p = rng.randrange(1, len(w))
    op = rng.choice("dsi")
    if op == "d":
        w = w[:p] + w[p + 1:]
    elif op == "s":
        w = w[:p] + rng.choice("aeiounhgtc") + w[p + 1:]
    else:
        w = w[:p] + w[p] + w[p:]
    words[i] = w
    return " ".join(words)


def _abbreviate(text):
    return (text.replace("Phường ", "P.").replace("Xã ", "X.")
                .replace("Thành phố ", "TP.").replace("Tỉnh ", "T."))


NOISE = [
    ("bo dau", lambda rng, a: _strip_accents(a)),
    ("bo dau phay", lambda rng, a: a.replace(",", "")),
    ("viet tat P. X. TP. T.", lambda rng, a: _abbreviate(a)),
    ("chu thuong", lambda rng, a: a.lower()),
    ("chu HOA", lambda rng, a: a.upper()),
    ("go sai 1 ky tu", _typo),
    ("tron tat ca", lambda rng, a: _typo(rng, _strip_accents(
        a.replace("Phường ", "P ").replace("Thành phố ", "TP")).lower())),
]


class TestPublic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.solver = _load_solver()
        cls.cases = _load_cases()

    def test_tung_mau_dung_ca_3_truong(self):
        for case in self.cases:
            with self.subTest(address=case["address"]):
                self.assertEqual(self.solver.process(case["address"]), case["result"])

    def test_diem_va_runtime(self):
        samples = [(c["address"], c["result"]) for c in self.cases]
        correct, total, worst, avg, _ = _run(self.solver, samples)
        _report("PUBLIC TEST cua thay (gioi han: max <= %.2f s, avg <= %.2f s)" % (MAX_TIME, AVG_TIME),
                [("public.json", correct, total, 10.0 * correct / total, worst, avg)])
        self.assertLessEqual(worst, MAX_TIME)
        self.assertLessEqual(avg, AVG_TIME)

    def test_gia_tri_tra_ve_nam_trong_db_cua_thay(self):
        db = {}
        for field in FIELDS:
            with open(os.path.join(PUBLIC, "list_%s.txt" % field), encoding="utf-8-sig") as f:
                db[field] = {line.strip() for line in f}
        for case in self.cases:
            for field, value in self.solver.process(case["address"]).items():
                if value:
                    self.assertIn(value, db[field], case["address"])


class TestPublicNhieu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.solver = _load_solver()
        cls.cases = _load_cases()
        cls.rows = []

    @classmethod
    def tearDownClass(cls):
        _report("PUBLIC TEST lam nhieu (yeu cau score/10 >= %.1f, max <= %.2f s, avg <= %.2f s)"
                % (MIN_NOISY_SCORE, MAX_TIME, AVG_TIME), cls.rows)

    def test_tung_kieu_nhieu(self):
        for name, noise in NOISE:
            rng = random.Random(1)
            samples = [(noise(rng, c["address"]), c["result"]) for c in self.cases]
            correct, total, worst, avg, wrong = _run(self.solver, samples)
            score = 10.0 * correct / total
            self.rows.append((name, correct, total, score, worst, avg))
            with self.subTest(nhieu=name):
                self.assertGreaterEqual(score, MIN_NOISY_SCORE, wrong[:5])
                self.assertLessEqual(worst, MAX_TIME)
                self.assertLessEqual(avg, AVG_TIME)


if __name__ == "__main__":
    unittest.main()
