# -*- coding: utf-8 -*-
"""Test input bất quy tắc, đo runtime theo giới hạn của đề, và kiểm tra format nộp theo slide.

Chạy:  python -m unittest tests.test_irregular -v      (đứng ở thư mục gốc dự án)
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import benchmark  # noqa: E402
from solution import FIELDS, NOT_FOUND, Solution  # noqa: E402

CASES_PATH = os.path.join(ROOT, "tests", "test_cases.json")

# Giới hạn ở slide 11 ("3. REQUIREMENTS")
MAX_TIME = 0.1
AVG_TIME = 0.01

HCM = "Thành phố Hồ Chí Minh"
NKKN, BT = "Nam Kỳ Khởi Nghĩa", "Phường Bến Thành"
FULL = (NKKN, BT, HCM)
BASE = "63 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh"

# (mô tả, input, (street, ward, province)) – chạy với DB mẫu trong data/
IRREGULAR = [
    # --- dấu phẩy / khoảng trắng
    ("không cách sau dấu phẩy", "63 Nam Kỳ Khởi Nghĩa,Phường Bến Thành,Thành phố Hồ Chí Minh", FULL),
    ("nhiều khoảng trắng liền nhau", "63   Nam  Kỳ   Khởi Nghĩa ,  Phường   Bến Thành  ,  Thành phố Hồ Chí Minh  ", FULL),
    ("khoảng trắng đầu/cuối + chấm cuối câu", "   " + BASE + ".", FULL),
    ("dấu phẩy thừa khắp nơi", ",,, 63 Nam Kỳ Khởi Nghĩa,,, Phường Bến Thành,,, TP HCM ,,,", FULL),
    ("tab và xuống dòng", "63 Nam Kỳ Khởi Nghĩa\tPhường Bến Thành\nTP HCM", FULL),
    ("xuống dòng kiểu Windows", "63 Nam Kỳ Khởi Nghĩa\r\nPhường Bến Thành\r\nTP HCM", FULL),
    ("khoảng trắng không ngắt (NBSP)", "63 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, TP HCM", FULL),
    ("ký tự rộng 0 (zero-width space)", "63 Nam Kỳ Khởi Nghĩa, Phường Bến​Thành, TP HCM", FULL),
    ("OCR tách từng chữ", "B ế n  T h à n h, H ồ  C h í  M i n h", ("", BT, HCM)),
    # --- dấu chấm
    ("chấm sau mọi từ", "63. Nam. Kỳ. Khởi. Nghĩa. Phường. Bến. Thành. Thành. phố. Hồ. Chí. Minh.", FULL),
    ("ba chấm thay dấu phẩy", "...63 Nam Kỳ Khởi Nghĩa...Phường Bến Thành...TP.HCM...", FULL),
    ("P. có khoảng trắng hai bên dấu chấm", "P . Bến Thành , TP . HCM", ("", BT, HCM)),
    ("P. rồi nhiều khoảng trắng", "P.  Bến Thành", ("", BT, NOT_FOUND)),
    ("TP. H.C.M (chấm giữa các chữ viết tắt)", "TP. H.C.M", ("", "", HCM)),
    ("T.P HCM", "T.P HCM", ("", "", HCM)),
    ("Tp.Hồ Chí Minh dính chấm", "Tp.Hồ Chí Minh", ("", "", HCM)),
    ("P.xxx,Q.1,TP.HCM không khoảng trắng", "P.Bến Thành,Q.1,TP.HCM", ("", BT, HCM)),
    # --- ký tự phân cách khác
    ("chấm phẩy", "63 Nam Kỳ Khởi Nghĩa; Phường Bến Thành; TP. HCM", FULL),
    ("gạch ngang", "63 Nam Kỳ Khởi Nghĩa - Phường Bến Thành - TP.HCM", FULL),
    ("gạch đứng", "63 Nam Kỳ Khởi Nghĩa | P.Bến Thành | TP.HCM", FULL),
    ("gạch chéo giữa các phần", "63 Nam Kỳ Khởi Nghĩa / Bến Thành / Hồ Chí Minh", FULL),
    ("ngoặc tròn", "63 Nam Kỳ Khởi Nghĩa (Phường Bến Thành), TP HCM", FULL),
    ("ngoặc kép, nháy đơn, ngoặc vuông", "\"63 Nam Kỳ Khởi Nghĩa\", 'Phường Bến Thành', [TP HCM]", FULL),
    ("ký tự lạ # @ *", "#63 Nam Kỳ Khởi Nghĩa @Bến Thành *HCM*", FULL),
    ("emoji", "63 Nam Kỳ Khởi Nghĩa 🏠 Bến Thành, HCM", FULL),
    # --- số nhà
    ("số nhà có chữ 63/12A", "63/12A Nam Kỳ Khởi Nghĩa, Bến Thành, HCM", FULL),
    ("số nhà chữ số toàn chiều rộng", "６３ Nam Kỳ Khởi Nghĩa, Bến Thành, HCM", FULL),
    # --- hoa thường, Unicode
    ("viết thường hết", "63 nam kỳ khởi nghĩa phường bến thành tp hcm", FULL),
    ("HOA không dấu", "63 NAM KY KHOI NGHIA P BEN THANH TP HCM", FULL),
    ("Unicode tổ hợp (NFD, hay gặp khi copy từ macOS)", unicodedata.normalize("NFD", BASE), FULL),
    ("có chữ đường/phường/thành phố viết thường + Việt Nam",
     "Số 63, đường Nam Kỳ Khởi Nghĩa, phường Bến Thành, thành phố Hồ Chí Minh, Việt Nam", FULL),
]

# input không có địa chỉ -> phải trả về 3 trường rỗng, không lỗi
EMPTY_INPUTS = ["", "   ", "\n\t", "...", ",,,", "!!!???", "12345", "-", None]


def _long_inputs():
    note = "Tầng 5, Tòa nhà ABC, ghi chú: giao hàng giờ hành chính, gọi trước khi giao "
    return [note * 2 + BASE, note * 10 + BASE, note * 25 + BASE, BASE * 20, "a" * 3000, "phuong " * 400]


class TestInputBatQuyTac(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.solver = Solution()

    def test_dau_cham_khoang_trang_ky_tu_la(self):
        for note, address, (street, ward, province) in IRREGULAR:
            with self.subTest(note=note, address=address):
                self.assertEqual(self.solver.process(address),
                                 {"street": street, "ward": ward, "province": province})

    def test_input_khong_co_dia_chi(self):
        for address in EMPTY_INPUTS:
            with self.subTest(address=address):
                self.assertEqual(self.solver.process(address), {f: NOT_FOUND for f in FIELDS})

    def test_input_rat_dai_khong_loi(self):
        for address in _long_inputs():
            with self.subTest(length=len(address)):
                out = self.solver.process(address)
                self.assertEqual(list(out), list(FIELDS))

    def test_ket_qua_on_dinh(self):
        for _, address, _ in IRREGULAR:
            self.assertEqual(self.solver.process(address), self.solver.process(address))


class TestRuntime(unittest.TestCase):
    """Đo runtime với DB cỡ thật của đề (~23.800 đường, ~3.300 phường/xã, 34 tỉnh) và in bảng kết quả."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.paths = benchmark.make_big_db(cls.tmp)
        t0 = time.perf_counter()
        cls.solver = Solution(**cls.paths)
        cls.init_time = time.perf_counter() - t0
        with open(CASES_PATH, encoding="utf-8") as f:
            cases = [c["address"] for c in json.load(f)]
        cls.groups = [
            ("test_cases.json", cases),
            ("input bat quy tac", [a for _, a, _ in IRREGULAR] + EMPTY_INPUTS),
            ("2000 dia chi nhieu", [a for a, _ in benchmark.make_noisy_samples(cls.paths, 2000)]),
            ("input rat dai (200-3000 ky tu)", _long_inputs()),
        ]
        cls.report = []

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        # in bằng chữ không dấu để console nào cũng đọc được
        lines = ["", "RUNTIME (gioi han: max <= %.2f s, avg <= %.2f s), khoi tao DB %.2f s:"
                 % (MAX_TIME, AVG_TIME, cls.init_time),
                 "  %-30s %6s %10s %10s  %s" % ("bo input", "so", "max (s)", "avg (s)", "ket qua")]
        lines += ["  %-30s %6d %10.4f %10.4f  %s" % row for row in cls.report]
        sys.stderr.write("\n".join(lines) + "\n\n")

    def _measure(self, addresses):
        self.solver.process(addresses[0])  # làm nóng
        times = []
        for address in addresses:
            t0 = time.perf_counter()
            self.solver.process(address)
            times.append(time.perf_counter() - t0)
        return max(times), sum(times) / len(times)

    def test_runtime_tung_bo(self):
        for name, addresses in self.groups:
            worst, avg = self._measure(addresses)
            # input rất dài chỉ cần dưới giới hạn max; trung bình tính trên các bộ địa chỉ bình thường
            check_avg = not name.startswith("input rat dai")
            ok = worst <= MAX_TIME and (avg <= AVG_TIME or not check_avg)
            self.report.append((name, len(addresses), worst, avg, "DAT" if ok else "VUOT"))
            with self.subTest(bo=name):
                self.assertLessEqual(worst, MAX_TIME)
                if check_avg:
                    self.assertLessEqual(avg, AVG_TIME)


class TestFormatNop(unittest.TestCase):
    """Đối chiếu với slide: format JSON (slide 8), yêu cầu nộp bài (slide 11)."""

    @classmethod
    def setUpClass(cls):
        cls.solver = Solution()

    def test_output_dung_3_khoa_theo_thu_tu_slide_8(self):
        out = self.solver.process(BASE)
        self.assertIsInstance(out, dict)
        self.assertEqual(list(out), ["street", "ward", "province"])
        self.assertTrue(all(isinstance(v, str) for v in out.values()))

    def test_3_vi_du_cua_slide_8(self):
        for address in ("63 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh",
                        "56/33 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh",
                        "69/49/59 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh"):
            self.assertEqual(self.solver.process(address),
                             {"street": NKKN, "ward": BT, "province": HCM})

    def test_output_ghi_ra_json_giong_slide_8(self):
        record = {"address": BASE, "result": self.solver.process(BASE)}
        text = json.dumps([record], ensure_ascii=False, indent=4)
        self.assertIn('"street": "Nam Kỳ Khởi Nghĩa"', text)
        self.assertEqual(json.loads(text), [record])

    def test_gia_tri_tra_ve_lay_nguyen_van_trong_db(self):
        db = {}
        for field, path in (("street", self.solver.street_path), ("ward", self.solver.ward_path),
                            ("province", self.solver.province_path)):
            with open(path, encoding="utf-8-sig") as f:
                db[field] = {line.strip() for line in f}
        with open(CASES_PATH, encoding="utf-8") as f:
            addresses = [c["address"] for c in json.load(f)] + [a for _, a, _ in IRREGULAR]
        for address in addresses:
            for field, value in self.solver.process(address).items():
                if value != NOT_FOUND:
                    self.assertIn(value, db[field], address)

    def test_file_test_dung_dinh_dang_slide_8(self):
        with open(CASES_PATH, encoding="utf-8") as f:
            cases = json.load(f)
        self.assertIsInstance(cases, list)
        for case in cases:
            self.assertIsInstance(case["address"], str)
            self.assertEqual(sorted(case["result"]), ["province", "street", "ward"])

    def test_db_34_tinh_utf8(self):
        # slide 7: 34 provinces
        for path in (self.solver.province_path, self.solver.ward_path, self.solver.street_path):
            with open(path, "rb") as f:
                raw = f.read()
            self.assertTrue(raw.strip(), path)
            raw.decode("utf-8")
        with open(self.solver.province_path, encoding="utf-8-sig") as f:
            self.assertEqual(len([line for line in f if line.strip()]), 34)

    def test_chay_duoc_khi_dung_o_thu_muc_khac(self):
        # máy chấm có thể chạy từ thư mục khác: Solution() phải tự tìm data/ cạnh solution.py
        code = ("import sys, json; sys.path.insert(0, %r); from solution import Solution; "
                "print(json.dumps(Solution().process(%r)))" % (ROOT, BASE))
        out = subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(),
                             capture_output=True, check=True)
        self.assertEqual(json.loads(out.stdout.decode("utf-8")), {"street": NKKN, "ward": BT, "province": HCM})

    def test_chi_dung_thu_vien_chuan_khong_ml_khong_internet(self):
        # slide 11: chạy trên máy không có internet, không dùng machine learning
        if not hasattr(sys, "stdlib_module_names"):
            self.skipTest("cần Python >= 3.10 để lấy danh sách thư viện chuẩn")
        local = {"solution", "benchmark", "evaluate"}
        banned = {"socket", "urllib", "http", "ftplib", "smtplib", "ssl"}
        for name in ("solution.py", "evaluate.py", "benchmark.py"):
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                else:
                    continue
                for module in modules:
                    top = module.split(".")[0]
                    with self.subTest(file=name, module=module):
                        self.assertTrue(top in sys.stdlib_module_names or top in local)
                        self.assertNotIn(top, banned)

    def test_co_readme_huong_dan_chay(self):
        # slide 11: Readme (how to run) chi tiết, dễ hiểu
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        for needle in ("python -m unittest", "python evaluate.py", "from solution import Solution",
                       "list_province.txt", "list_ward.txt", "list_street.txt"):
            self.assertIn(needle, readme)


if __name__ == "__main__":
    unittest.main()
