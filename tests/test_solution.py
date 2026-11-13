# -*- coding: utf-8 -*-
"""Chạy:  python -m unittest discover -s tests -v   (đứng ở thư mục gốc dự án)"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from solution import STREET, Solution, Trie, analyze  # noqa: E402
import benchmark  # noqa: E402

CASES_PATH = os.path.join(ROOT, "tests", "test_cases.json")


def _write_db(folder, streets, wards, provinces):
    paths = []
    for name, items in (("street", streets), ("ward", wards), ("province", provinces)):
        path = os.path.join(folder, "list_%s.txt" % name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(items) + "\n")
        paths.append(path)
    return paths


class TestAnalyze(unittest.TestCase):
    def test_bo_dau_va_khoang_trang(self):
        S, A, _, _, tokens = analyze("Phường Bến Thành")
        self.assertEqual(S, "phuongbenthanh")
        self.assertEqual(A, "phườngbếnthành")
        self.assertEqual(tokens, [(0, 6), (6, 9), (9, 14)])

    def test_chu_d_gach(self):
        self.assertEqual(analyze("Đường Đống Đa")[0], "duongdongda")

    def test_dau_cau_la_ranh_gioi(self):
        S, _, _, bound, tokens = analyze("TP.HCM")
        self.assertEqual(S, "tphcm")
        self.assertEqual(tokens, [(0, 2), (2, 5)])
        self.assertEqual(list(bound), [1, 0, 1, 0, 0, 1])

    def test_tach_camel_case(self):
        S, _, _, _, tokens = analyze("NamKỳKhởiNghĩa")
        self.assertEqual([S[a:b] for a, b in tokens], ["nam", "ky", "khoi", "nghia"])

    def test_tach_so_va_chu(self):
        S, _, _, _, tokens = analyze("45LêLợi 56/33")
        self.assertEqual([S[a:b] for a, b in tokens], ["45", "le", "loi", "56/33"])


class TestTrie(unittest.TestCase):
    def setUp(self):
        self.trie = Trie()
        self.trie.insert("ben", 2)
        self.trie.insert("benthanh", 1)
        self.trie.insert("hochiminh", 3)

    def test_exact_tra_moi_khoa_la_tien_to(self):
        self.assertEqual(self.trie.exact("benthanhxyz", 0, 11), [(3, [2], 0), (8, [1], 0)])

    def test_exact_dung_o_end(self):
        self.assertEqual(self.trie.exact("benthanh", 0, 5), [(3, [2], 0)])

    def test_fuzzy_thieu_ky_tu(self):
        self.assertIn((7, [1], 1), self.trie.fuzzy("benthan", 0, 7))

    def test_fuzzy_sai_ky_tu(self):
        self.assertIn((9, [3], 1), self.trie.fuzzy("hochimimh", 0, 9))

    def test_fuzzy_khoa_ngan_phai_khop_tuyet_doi(self):
        self.assertEqual([m for m in self.trie.fuzzy("bem", 0, 3) if m[1] == [2]], [])

    def test_fuzzy_ky_tu_dau_phai_dung(self):
        self.assertEqual(self.trie.fuzzy("venthanh", 0, 8), [])


class TestExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.solver = Solution()
        with open(CASES_PATH, encoding="utf-8") as f:
            cls.cases = json.load(f)

    def test_bo_test_case(self):
        for case in self.cases:
            with self.subTest(note=case.get("note"), address=case["address"]):
                self.assertEqual(self.solver.process(case["address"]), case["result"])

    def test_ho_duong_khong_bi_cat_nhu_tien_to(self):
        # DB "Dương Bá Trạc": "Dương" là họ, không phải "Đường" -> khoá phải là "duongbatrac"
        trie = self.solver.tries[STREET]
        self.assertTrue(trie.exact("duongbatrac", 0, 11))
        self.assertFalse(trie.exact("batrac", 0, 6))

    def test_dinh_dang_output(self):
        out = self.solver.process("63 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh")
        self.assertEqual(sorted(out), ["province", "street", "ward"])
        self.assertTrue(all(isinstance(v, str) for v in out.values()))


class TestSlide6(unittest.TestCase):
    """Hai ví dụ ở slide 6: cùng input, DB khác nhau -> output lấy đúng chuỗi trong DB."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _solve(self, streets, wards, provinces):
        folder = tempfile.mkdtemp(dir=self.tmp)
        street, ward, province = _write_db(folder, streets, wards, provinces)
        solver = Solution(province_path=province, ward_path=ward, street_path=street)
        return solver.process("268 Lý Thường Kiệt, Diên Hồng, TP. HCM")

    def test_vi_du_1(self):
        out = self._solve(["Lý Thường Kiệt", "Sư Vạn Hạnh", "3/2"],
                          ["Diên Hồng", "Hòa Hưng", "Con cò bé bé"],
                          ["TP. HCM", "Hà Nội", "Vũng Tàu"])
        self.assertEqual(out, {"street": "Lý Thường Kiệt", "ward": "Diên Hồng", "province": "TP. HCM"})

    def test_vi_du_2(self):
        out = self._solve(["LTK", "Sư Vạn Hạnh", "3/2"],
                          ["Hòa Hưng", "Con cò bé bé"],
                          ["TP. Hồ Chí Minh", "Hà Nội", "Vũng Tàu"])
        self.assertEqual(out, {"street": "LTK", "ward": "", "province": "TP. Hồ Chí Minh"})


class TestTrungTenVoiDBLon(unittest.TestCase):
    """Các lỗi bắt nhầm đã gặp khi chạy benchmark với DB ~27.000 tên (tên đường ở đây là giả)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        street, ward, province = _write_db(
            cls.tmp,
            ["Lê Lợi", "Hạnh Thịnh", "Kiều Hòa Uyên", "Phú Long", "Phong Ngọc",
             "Nam Kỳ", "Nam Kỳ Khởi Nghĩa", "Dương Minh", "Minh", "Toàn Tín"],
            ["Phường Bến Thành", "Phường Ngọc Hà", "Phường Ba Đình", "Phường Tân Định", "Phường Quý Toàn"],
            ["Thành phố Hồ Chí Minh", "Thành phố Hà Nội", "Tỉnh Cao Bằng"])
        cls.solver = Solution(province_path=province, ward_path=ward, street_path=street)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, address, street, ward, province):
        self.assertEqual(self.solver.process(address),
                         {"street": street, "ward": ward, "province": province})

    def test_sua_loi_ca_khi_luot_1_da_khop_ten_ngan_hon(self):
        self.check("63 Nam Ky Khoi Ngia, Phuong Ben Thanh, TP HCM",
                   "Nam Kỳ Khởi Nghĩa", "Phường Bến Thành", "Thành phố Hồ Chí Minh")

    def test_luot_1_khop_nham_khong_chan_luot_2(self):
        # lượt 1 khớp nhầm đường "Toàn Tín" trong "Toàn Tỉnh"
        self.check("P.Quýý Toàn Tỉnh Cao Bằng", "", "Phường Quý Toàn", "Tỉnh Cao Bằng")

    def test_tu_khoa_khong_bi_sua_thanh_ten(self):
        self.check("Phuong Ngoc Ha, Ba Dinh, Ha Noi", "", "Phường Ngọc Hà", "Thành phố Hà Nội")
        self.check("Phuờng Tân Đinh, Thàn phố Hồ Chí Minh", "", "Phường Tân Định", "Thành phố Hồ Chí Minh")

    def test_viet_tat_duong_phai_viet_hoa(self):
        self.check("123 Đường ABC, Khu phố 3, TP HCM", "", "", "Thành phố Hồ Chí Minh")
        self.check("12 KHU, P. Bến Thành, TP HCM", "Kiều Hòa Uyên", "Phường Bến Thành", "Thành phố Hồ Chí Minh")

    def test_uu_tien_ten_duong_sau_so_nha(self):
        self.check("Giao hàng giờ hành chính - 45 Lê Lợi, P Bến Thành, HCM",
                   "Lê Lợi", "Phường Bến Thành", "Thành phố Hồ Chí Minh")

    def test_ho_duong_khong_phai_duong(self):
        self.check("12 Dương Minh, P. Bến Thành, TP HCM", "Dương Minh", "Phường Bến Thành", "Thành phố Hồ Chí Minh")

    def test_hien_test1(self):
        self.check("", "", "", "")

    def test_hien_test2(self):
        self.check("xyz", "", "", "")

    def test_hien_test3(self):
        self.check(".", "", "", "")

class TestSpeed(unittest.TestCase):
    """Yêu cầu đề: tối đa 0.1 s / request, trung bình 0.01 s / request, với DB cỡ thật."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.paths = benchmark.make_big_db(cls.tmp)
        cls.solver = Solution(**cls.paths)
        with open(CASES_PATH, encoding="utf-8") as f:
            cls.addresses = [c["address"] for c in json.load(f)]
        cls.addresses += [a for a, _ in benchmark.make_noisy_samples(cls.paths, 1500)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_thoi_gian(self):
        times = []
        for address in self.addresses:
            t0 = time.perf_counter()
            self.solver.process(address)
            times.append(time.perf_counter() - t0)
        self.assertLess(max(times), 0.1)
        self.assertLess(sum(times) / len(times), 0.01)


if __name__ == "__main__":
    unittest.main()
