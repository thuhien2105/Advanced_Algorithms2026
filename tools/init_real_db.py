# -*- coding: utf-8 -*-
"""Dựng nhanh data_real/ cỡ 34 tỉnh x 10 phường/xã x 10 tên đường (không cần Overpass).

  - Tỉnh, phường/xã: tên THẬT sau sắp xếp 2025, lấy từ https://provinces.open-api.vn/api/v2/
    (cache trong tools/.cache/, chạy lại không phải tải).
  - Tên đường: mỗi phường 10 tên KHÔNG TRÙNG trong toàn DB (đủ 34 x 10 x 10 = 3400 tên để dựng Trie
    đúng cỡ): ~300 tên đường phổ biến có thật ở VN (STREETS), phần còn lại sinh theo mẫu Họ + đệm + tên.
    Không đảm bảo con đường đó nằm đúng trong phường, nhưng đủ để đo tốc độ / độ chính xác.
  - Tên phường/xã cũng không trùng giữa các tỉnh (đủ 340 tên).

    python tools/init_real_db.py                  # ghi vào data_real/
    python tools/init_real_db.py --seed 7 --wards 10 --streets 10
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_real_db import API, ROOT, _get   # noqa: E402

STREETS = """
Lê Lợi|Lê Lai|Lê Duẩn|Lê Thánh Tôn|Lê Hồng Phong|Lê Văn Sỹ|Lê Quang Định|Lê Đại Hành|Lê Văn Việt|Lê Thị Riêng
Nguyễn Huệ|Nguyễn Trãi|Nguyễn Du|Nguyễn Thị Minh Khai|Nguyễn Đình Chiểu|Nguyễn Văn Cừ|Nguyễn Văn Linh|Nguyễn Chí Thanh
Nguyễn Thái Học|Nguyễn Công Trứ|Nguyễn Văn Trỗi|Nguyễn Tri Phương|Nguyễn Oanh|Nguyễn Kiệm|Nguyễn Sơn|Nguyễn Khuyến
Nguyễn Bỉnh Khiêm|Nguyễn Thiện Thuật|Nguyễn Văn Đậu|Nguyễn Hữu Cảnh|Nguyễn Tất Thành|Nguyễn Lương Bằng|Nguyễn Văn Bé
Trần Hưng Đạo|Trần Phú|Trần Quốc Toản|Trần Nhân Tông|Trần Khát Chân|Trần Cao Vân|Trần Quang Khải|Trần Duy Hưng
Trần Bình Trọng|Trần Não|Trần Xuân Soạn|Trần Văn Ơn|Trần Đại Nghĩa|Trần Quốc Thảo|Trần Thái Tông|Trần Đăng Ninh
Hai Bà Trưng|Bà Triệu|Lý Thường Kiệt|Lý Thái Tổ|Lý Tự Trọng|Lý Chính Thắng|Lý Nam Đế|Lý Thánh Tông
Quang Trung|Hùng Vương|Ngô Quyền|Đinh Tiên Hoàng|Lê Hoàn|Phan Bội Châu|Phan Chu Trinh|Phan Đình Phùng
Phan Xích Long|Phan Văn Trị|Phan Đăng Lưu|Phan Huy Ích|Phan Kế Bính|Phạm Văn Đồng|Phạm Ngũ Lão|Phạm Hùng
Phạm Văn Bạch|Phạm Thế Hiển|Phạm Ngọc Thạch|Võ Văn Tần|Võ Thị Sáu|Võ Nguyên Giáp|Võ Văn Kiệt|Võ Thị Văn
Hoàng Văn Thụ|Hoàng Diệu|Hoàng Hoa Thám|Hoàng Quốc Việt|Hoàng Sa|Trường Sa|Hoàng Văn Bồn|Hoàng Minh Giám
Điện Biên Phủ|Cách Mạng Tháng Tám|Ba Tháng Hai|Ba Mươi Tháng Tư|Mười Chín Tháng Năm|Hai Tháng Chín
Nam Kỳ Khởi Nghĩa|Đồng Khởi|Tôn Đức Thắng|Tôn Thất Thuyết|Tôn Thất Tùng|Huỳnh Thúc Kháng|Huỳnh Tấn Phát
Huỳnh Văn Bánh|Cống Quỳnh|Calmette|Pasteur|Yersin|Alexandre de Rhodes|Nam Quốc Cang|Mạc Đĩnh Chi|Mạc Thị Bưởi
Đinh Bộ Lĩnh|Đinh Công Tráng|Đoàn Thị Điểm|Đoàn Văn Bơ|Đào Duy Anh|Đào Duy Từ|Đào Tấn|Đặng Văn Ngữ|Đặng Tất
Đặng Dung|Đặng Thái Thân|Đỗ Xuân Hợp|Đỗ Quang|Bùi Thị Xuân|Bùi Viện|Bùi Hữu Nghĩa|Cao Thắng|Cao Bá Quát
Chu Văn An|Chu Văn Thịnh|Cô Bắc|Cô Giang|Dương Bá Trạc|Dương Đình Nghệ|Dương Quảng Hàm|Giải Phóng|Hàng Bài
Hàng Bạc|Hàng Bông|Hàng Đào|Hàng Gai|Hàng Ngang|Hàng Trống|Tràng Tiền|Tràng Thi|Hồ Tùng Mậu|Hồ Xuân Hương
Hồ Văn Huê|Hồ Biểu Chánh|Kim Mã|Khâm Thiên|Kha Vạn Cân|Khánh Hội|Kỳ Đồng|Lạc Long Quân|Láng Hạ|Lãnh Binh Thăng
Lương Định Của|Lương Thế Vinh|Lương Văn Can|Lương Ngọc Quyến|Mai Hắc Đế|Mai Thị Lựu|Minh Khai|Nam Cao
Ngô Gia Tự|Ngô Tất Tố|Ngô Thời Nhiệm|Ngô Đức Kế|Ngô Văn Năm|Nơ Trang Long|Nam Kỳ|Ông Ích Khiêm|Pháo Đài Láng
Phó Đức Chính|Phùng Hưng|Phùng Khắc Khoan|Quán Thánh|Sư Vạn Hạnh|Thái Hà|Thái Văn Lung|Thành Thái|Thích Quảng Đức
Thoại Ngọc Hầu|Thống Nhất|Tô Hiến Thành|Tô Ngọc Vân|Tô Vĩnh Diện|Trương Định|Trương Công Định|Trương Hán Siêu
Trương Văn Bang|Trịnh Hoài Đức|Trịnh Đình Thảo|Trường Chinh|Văn Cao|Vạn Kiếp|Vũ Tông Phan|Vũ Huy Tấn|Xô Viết Nghệ Tĩnh
Xuân Thủy|Xuân Diệu|Yên Phụ|Âu Cơ|Âu Dương Lân|Ỷ Lan|An Dương Vương|Bạch Đằng|Bạch Mai|Bế Văn Đàn|Cù Chính Lan
Chi Lăng|Cửa Bắc|Cửa Nam|Duy Tân|Đội Cấn|Độc Lập|Giảng Võ|Hàn Thuyên|Hòa Bình|Hòa Hảo|Kim Đồng|La Thành
Lạc Trung|Lam Sơn|Lãn Ông|Lê Ngô Cát|Lý Văn Phức|Mã Mây|Nguyễn Biểu|Nguyễn Cảnh Chân|Nguyễn Gia Thiều|Nguyễn Hoàng
Nguyễn Phong Sắc|Nguyễn Văn Huyên|Nguyễn Xiển|Quốc Tử Giám|Tạ Quang Bửu|Tây Sơn|Thanh Niên|Thụy Khuê|Tôn Đản
Trần Hữu Trang|Triệu Việt Vương|Tuệ Tĩnh|Vũ Ngọc Phan|Vũ Trọng Phụng|Hòa Mã|Cầu Giấy|Kim Ngưu|Lò Đúc|Nguyễn An Ninh
Bến Vân Đồn|Tân Kỳ Tân Quý|Tân Sơn Nhì|Âu Văn Cẩn|Bình Giã|Bàu Cát|Cộng Hòa|Dân Chủ|Độc Lập|Hồng Bàng|Hậu Giang
Kinh Dương Vương|Lũy Bán Bích|Lạc Hồng|Phú Thọ Hòa|Quang Trung|Tỉnh Lộ 10|Quốc Lộ 1A|Quốc Lộ 13|Quốc Lộ 50|Đường số 5
Đường số 7|Đường 3/2|Hàm Nghi|Hàm Tử|Mai Chí Thọ|Song Hành|Tân Lập|Tân Hòa Đông|Trần Văn Giàu|Vĩnh Viễn
""".replace("\n", "|").split("|")
STREETS = list(dict.fromkeys(s.strip() for s in STREETS if s.strip()))

# Tên đường VN phần lớn là tên người: Họ + tên đệm + tên. Dùng để bù cho đủ số tên KHÔNG TRÙNG.
HO = ("Nguyễn Trần Lê Phạm Hoàng Huỳnh Phan Vũ Võ Đặng Bùi Đỗ Hồ Ngô Dương Lý Đinh Lâm Trương Mai "
      "Tạ Cao Đoàn Tô Lương Hà Thái Châu Trịnh Kiều").split()
DEM = "Văn|Thị|Hữu|Đức|Công|Quang|Minh|Xuân|Thanh|Ngọc|Đình|Bá|Thế|Quốc|Tấn".split("|")
TEN = ("An Bình Cường Dũng Đạt Hải Hiếu Hòa Hùng Huy Khang Khoa Lâm Long Lộc Luân Minh Nam Nghĩa Nhân Phát "
       "Phong Phúc Quân Sang Sơn Tài Tâm Thắng Thành Thịnh Thông Tiến Toàn Trí Trung Tuấn Tùng Uy Vinh Vũ "
       "Bảo Châu Chiến Định Giang Hạnh Hiển Khải Kiên Lợi Mạnh Ninh Quý Tín Triều Tường Viên Yên").split()


def street_pool(rng, need):
    """>= need tên đường KHÔNG TRÙNG (kể cả khi bỏ dấu): danh sách thật trước, rồi Họ + đệm + tên."""
    import unicodedata

    def plain(s):
        s = s.replace("đ", "d").replace("Đ", "D")
        return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if c.isalnum())

    seen, pool = set(), []
    combos = [f"{h} {d} {t}" for h in HO for d in DEM for t in TEN]
    rng.shuffle(combos)
    for s in STREETS + combos:
        if plain(s) not in seen:
            seen.add(plain(s))
            pool.append(s)
        if len(pool) >= need:
            break
    if len(pool) < need:
        raise SystemExit(f"chỉ sinh được {len(pool)} tên đường, cần {need}")
    real, extra = pool[:len(STREETS)], pool[len(STREETS):]
    rng.shuffle(real)
    return real + extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data_real"))
    ap.add_argument("--seed", type=int, default=2025)
    ap.add_argument("--wards", type=int, default=10)
    ap.add_argument("--streets", type=int, default=10)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    provinces = _get(API + "/p/")
    pool = street_pool(rng, len(provinces) * args.wards * args.streets)
    rows, used_wards = [], set()
    for p in provinces:
        detail = _get(f"{API}/p/{p['code']}?depth=2")
        wards = [w["name"] for w in detail["wards"] if w["name"] not in used_wards]  # tên phường không trùng
        rng.shuffle(wards)
        for ward in wards[:args.wards]:
            used_wards.add(ward)
            streets, pool = pool[:args.streets], pool[args.streets:]   # tên đường không trùng
            rows.append({"province": p["name"], "ward": ward, "streets": sorted(streets)})
        print(f"  {p['name']:28s} {len(detail['wards']):4d} phường/xã -> chọn {min(args.wards, len(wards))}")

    os.makedirs(args.out, exist_ok=True)
    streets = sorted({s for r in rows for s in r["streets"]})
    wards = sorted({r["ward"] for r in rows})
    for fname, items in (("list_province.txt", [p["name"] for p in provinces]),
                         ("list_ward.txt", wards), ("list_street.txt", streets)):
        with open(os.path.join(args.out, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(items) + "\n")
    with open(os.path.join(args.out, "addresses.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"xong: {len(provinces)} tỉnh, {len(wards)} phường/xã, {len(rows)} phường x {args.streets} đường "
          f"({len(streets)} tên đường không trùng) -> {args.out}")


if __name__ == "__main__":
    main()
