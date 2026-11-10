# -*- coding: utf-8 -*-
"""Chấm điểm giống bảng ở slide 10: correct, total (= 3 x số mẫu), score/10, max_time_sec, avg_time_sec.

    python evaluate.py                                    # chấm tests/test_cases.json
    python evaluate.py public_test.json --show-errors     # chấm file khác, in các trường sai
    python evaluate.py public_test.json --data ../data    # dùng DB ở thư mục khác

File test có dạng như slide 8:
    [{"address": "...", "result": {"street": "...", "ward": "...", "province": "..."}}, ...]
"""
import argparse
import json
import os
import time

from benchmark import use_utf8_stdout
from solution import FIELDS, Solution

ROOT = os.path.dirname(os.path.abspath(__file__))


def _same(got, want):
    """"" / None / "Null" đều nghĩa là không có."""
    empty = (None, "", "Null", "null")
    return (got in empty and want in empty) or got == want


def main():
    use_utf8_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("test_file", nargs="?", default=os.path.join(ROOT, "tests", "test_cases.json"))
    parser.add_argument("--data", help="thư mục chứa list_province.txt, list_ward.txt, list_street.txt")
    parser.add_argument("--name", default="Solution", help="tên hiển thị ở cột name")
    parser.add_argument("--show-errors", action="store_true")
    args = parser.parse_args()

    paths = {}
    if args.data:
        for key in ("province", "ward", "street"):
            paths[key + "_path"] = os.path.join(args.data, "list_%s.txt" % key)
    solver = Solution(**paths)

    with open(args.test_file, encoding="utf-8") as f:
        cases = json.load(f)

    correct, times, errors = 0, [], []
    for case in cases:
        t0 = time.perf_counter()
        out = solver.process(case["address"])
        times.append(time.perf_counter() - t0)
        for field in FIELDS:
            if _same(out[field], case["result"].get(field)):
                correct += 1
            else:
                errors.append((case["address"], field, out[field], case["result"].get(field)))

    total = 3 * len(cases)
    print("%-12s %8s %6s %9s %13s %13s" % ("name", "correct", "total", "score/10", "max_time_sec", "avg_time_sec"))
    print("%-12s %8d %6d %9.2f %13.4f %13.4f" % (args.name, correct, total, 10.0 * correct / max(total, 1),
                                                max(times or [0]), sum(times) / max(len(times), 1)))
    if args.show_errors:
        for address, field, got, want in errors:
            print("- %s\n    %s: got %r, want %r" % (address, field, got, want))


if __name__ == "__main__":
    main()
