# Address Segmentation: Trie + Quy hoạch động (DP)

Tách một chuỗi địa chỉ thành **đường (street) / phường-xã (ward) / tỉnh-thành (province)**,
lấy đúng tên có trong cơ sở dữ liệu (DB). Chỉ dùng thuật toán (Trie, DP, khoảng cách Levenshtein),
**không dùng machine learning**, chỉ cần thư viện chuẩn của Python, chạy không cần internet.

```json
{
  "address": "63 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh",
  "result": {
    "street": "Nam Kỳ Khởi Nghĩa",
    "ward": "Phường Bến Thành",
    "province": "Thành phố Hồ Chí Minh"
  }
}
```

- Giá trị trả về lấy **nguyên văn trong DB**. Ví dụ ở slide 6: DB lưu `LTK` thì input
  "Lý Thường Kiệt" trả về `LTK`; DB lưu `TP. Hồ Chí Minh` thì input "TP. HCM" trả về `TP. Hồ Chí Minh`.
- Trường nào không có trong DB thì trả `""`. Muốn đổi thành `"Null"` hay `None`, sửa hằng
  `NOT_FOUND` ở đầu [solution.py](solution.py).

---

## 1. Cấu trúc thư mục

```
address_segmentation/
├── solution.py            # lời giải: class Solution, hàm process(address) -> dict
├── data/                  # DB MẪU (minh hoạ), thay bằng DB thật của đề
│   ├── list_province.txt  #   34 tỉnh/thành sau sáp nhập 2025
│   ├── list_ward.txt      #   một ít phường/xã
│   └── list_street.txt    #   một ít tên đường
├── tests/
│   ├── test_cases.json    # 59 test case, định dạng giống slide 8
│   └── test_solution.py   # unit test + test thời gian
├── evaluate.py            # chấm điểm giống bảng ở slide 10
└── benchmark.py           # đo tốc độ với DB cỡ thật (~27.000 tên, sinh ngẫu nhiên)
```

Mỗi file trong `data/` có **một tên mỗi dòng**, mã hoá UTF-8 (có hay không có BOM đều được).
Tên có thể kèm tiền tố ("Phường Bến Thành") hoặc không ("Bến Thành"); dòng trống và dòng bắt đầu
bằng `#` bị bỏ qua.

> Dữ liệu trong `data/` chỉ là một mẫu nhỏ để chạy test, **không phải danh sách chính thức**.
> Khi có DB của đề, chép đè 3 file này (hoặc truyền đường dẫn, xem mục 2.1).

---

## 2. Cách chạy

Yêu cầu: **Python 3.7 trở lên**, không cần cài thêm gói nào. Mọi lệnh dưới đây chạy tại thư mục
`address_segmentation/`.

### 2.1. Dùng trong code

```python
from solution import Solution

solver = Solution()   # đọc data/list_province.txt, data/list_ward.txt, data/list_street.txt
print(solver.process("45 Lê Lơi, P. Bến Thàn, TP.HCM"))
# {'street': 'Lê Lợi', 'ward': 'Phường Bến Thành', 'province': 'Thành phố Hồ Chí Minh'}

# DB ở chỗ khác:
solver = Solution(province_path="db/provinces.txt",
                  ward_path="db/wards.txt",
                  street_path="db/streets.txt")
```

Khởi tạo `Solution()` (đọc DB, dựng Trie) chỉ làm **một lần**, sau đó gọi `process()` cho từng request.

### 2.2. Chạy test

```bash
python -m unittest discover -s tests -v
```

Gồm: test chuẩn hoá chuỗi, test Trie (khớp chính xác / gần đúng), 59 test case trong
`tests/test_cases.json`, 2 ví dụ ở slide 6, các lỗi bắt nhầm khi DB lớn, và test thời gian
(max ≤ 0.1 s, trung bình ≤ 0.01 s trên DB ~27.000 tên).

### 2.3. Chấm điểm giống slide 10

```bash
python evaluate.py
```

Chấm file khác, dùng DB ở thư mục khác, in các trường sai:

```bash
python evaluate.py path/to/public_test.json --data path/to/db --show-errors
```

`total = 3 × số mẫu` (mỗi mẫu 3 trường), `score/10 = 10 × correct / total`, giống bảng điểm ở slide 10.

### 2.4. Đo tốc độ với DB cỡ thật

```bash
python benchmark.py
```

Sinh ngẫu nhiên 23.800 tên đường + 3.300 phường/xã (cỡ DB của đề: 34 × 10 × 70 đường) rồi chạy
59 test case và 2.000 địa chỉ có nhiễu (bỏ dấu, viết tắt, lỗi chính tả, thiếu dấu phẩy).

---

## 3. Thuật toán

### 3.1. Chuẩn hoá chuỗi

| Bước | Ví dụ |
|---|---|
| Bỏ dấu, viết thường, `đ → d` | `Bến Thành` → `benthanh` |
| **Bỏ hết khoảng trắng và dấu câu** | `TP.HCM`, `TP HCM`, `TPHCM` → `tphcm` |
| Ghi lại **ranh giới từ** (mảng `bound`) | `TP.HCM` → ranh giới tại vị trí 0, 2, 5 |
| Tách từ khi đổi chữ ↔ số, hoặc chữ thường → HOA | `45LêLợi` → `45 / le / loi`, `ThuanThanh` → `thuan / thanh` |
| Giữ thêm bản **còn dấu** song song | để phân biệt `Thạnh` / `Thành` |

Nhờ bỏ khoảng trắng nên các lỗi OCR kiểu dính chữ (`ThuanThanh`, `T.Long An`, `HCần Giuộc`) và tách
chữ đều về cùng một dạng. Ranh giới từ vẫn được giữ để chấm điểm (mục 3.4).

### 3.2. Trie

Mỗi loại (street / ward / province) có **một Trie** (dict lồng nhau), khoá là tên đã chuẩn hoá:

- Bỏ tiền tố hành chính của tên trong DB: `Phường Bến Thành` → khoá `benthanh`, nhóm `phuong`.
  So cả dấu nên `Dương Minh` (họ Dương) **không** bị cắt như `Đường Minh`.
- Tên quá ngắn hoặc toàn số (`Phường 1`) thì bắt buộc kèm tiền tố: khoá `phuong1`, `p1`, `f1`.
- Thêm Trie **chữ cái đầu**: `Nam Kỳ Khởi Nghĩa` → `nkkn`, `Cách Mạng Tháng 8` → `cmt8`,
  `Thành phố Hồ Chí Minh` → `hcm`, `Thành phố Hà Nội` → `hn`.
- Tên DB là viết tắt (`LTK`) thì lưu vào bảng riêng, so với chữ cái đầu của các cụm từ trong input
  ("Lý Thường Kiệt" → `ltk`).

Ngoài ra có một Trie nhỏ cho **tiền tố hành chính**: `phường / p / f`, `xã / x`, `thị trấn / tt`,
`đặc khu / đk`, `thành phố / tp`, `tỉnh / t`, `đường / đ`, `phố`, và tiền tố cấp huyện cũ
`quận / q / huyện / h / thị xã / tx` (bỏ qua, không thưởng điểm).

### 3.3. Sinh ứng viên

Gọi `S` là chuỗi đã chuẩn hoá, độ dài `n`. Một **ứng viên** là bộ `(i, j, loại, điểm, tên)`, nghĩa là
đoạn `S[i:j]` (có thể gồm tiền tố + tên) khớp một tên trong DB.

**Lượt 1, khớp chính xác.** Với mỗi vị trí `i`:
1. Đi trên Trie tiền tố từ `i` để lấy các điểm `k` mà `S[i:k]` là tiền tố (kể cả `k = i`, không có tiền tố).
2. Từ mỗi `k`, đi dọc Trie của từng loại: mỗi nút kết thúc từ gặp trên đường đi cho một ứng viên `S[i:j]`.
   Mỗi lần đi tốn O(độ dài tên dài nhất).

**Lượt 2, khớp gần đúng** (chỉ chạy khi còn chữ cái chưa được ứng viên nào của lượt 1 giải thích).
Từ mỗi đầu từ, duyệt DFS trên Trie, **mỗi nút giữ một hàng của bảng DP Levenshtein**:

```
row_con[x] = min( row_cha[x-1] + (S[k+x-1] != ký tự của nút),   # khớp / sửa
                  row_cha[x]   + 1,                             # tên thừa 1 ký tự
                  row_con[x-1] + 1 )                            # input thừa 1 ký tự
```

Các tên chung tiền tố dùng chung phần tính toán. Để nhanh và ít bắt nhầm:
- chỉ tính trong dải `|x − độ sâu| ≤ 2`;
- ký tự đầu phải đúng, tối đa 1 lỗi trong 6 ký tự đầu (cắt nhánh sớm);
- số lỗi cho phép: tên ≤ 5 ký tự là 0, 6–10 ký tự là 1, ≥ 11 ký tự là 2;
- không sửa lỗi phần chữ số (`Phường 14` không thành `Phường 12`);
- không sửa lỗi khi đoạn bắt đầu bằng một từ khoá (`phuong` không thành tên `Phú Long`).

### 3.4. Chấm điểm một ứng viên

```
điểm = số ký tự phủ được
       − 2.5 × số lỗi chính tả
       − 1.5 nếu đầu đoạn nằm giữa một từ   − 1.5 nếu cuối đoạn nằm giữa một từ
       + 1.0 nếu có tiền tố đúng loại ("Phường" trước tên phường)
       + 2.0 nếu là tên đường đứng ngay sau số nhà
```

Ứng viên bị loại nếu điểm < max(2, ½ × số ký tự phủ), hoặc tên ≤ 3 ký tự (`hcm`, `hue`, `p1`)
mà không đứng thành từ riêng, hoặc `Phường 1` bị khớp vào `Phường 14`.

Khi nhiều tên trong DB trùng khoá không dấu (`Phường Bình Thạnh` / `Xã Bình Thành`), chọn tên
**cùng nhóm tiền tố** với input (`P.` → Phường, `X.` → Xã), rồi đến tên **giống dấu nhất** với input.

### 3.5. Quy hoạch động chọn kết quả

Chọn một tập ứng viên **không chồng nhau**, đúng thứ tự trong địa chỉ Việt Nam
**street → ward → province** (mỗi loại tối đa 1), sao cho tổng điểm lớn nhất:

```
best[p][st] = điểm lớn nhất khi đã đọc xong S[:p], st = 0 (chưa gán gì) hoặc 1 + loại vừa gán

best[p+1][st] ← best[p][st]                       # bỏ qua ký tự S[p] (số nhà, chữ nhiễu...)
best[j][t+1]  ← best[i][st] + điểm(i, j, t)       # nhận ứng viên S[i:j] loại t, với st ≤ t
```

Truy vết ngược từ `max(best[n][·])` để lấy 3 trường. Nhờ DP nên các trường hợp nhập nhằng được
giải quyết theo toàn cục, không theo từng đoạn riêng lẻ:

- `30 Hai Bà Trưng, Phường Tân Định, TP HCM`: "Hai Bà Trưng" là **đường** (vì phía sau còn phường).
- `Phường Hai Bà Trưng, Hà Nội`: "Hai Bà Trưng" là **phường** (có tiền tố "Phường").
- `Điện Biên Phủ, Phường Gia Định, TP HCM`: là đường Điện Biên Phủ, **không** phải tỉnh Điện Biên
  (tỉnh phải đứng cuối, và tên dài hơn được nhiều điểm hơn).

### 3.6. Độ phức tạp mỗi request

Với `n` ≈ 30–80 ký tự và `L` là độ dài tên dài nhất:
- Lượt 1: O(n · L), chỉ là các phép tra dict.
- Lượt 2: O(số đầu từ × số nút Trie được duyệt × 5); nhờ cắt nhánh nên chỉ duyệt một phần rất nhỏ của Trie.
- DP: O(4n + 4 × số ứng viên).

---

## 4. Kết quả

Đo trên máy phát triển (Python 3.14, Windows 11); thời gian dao động giữa các lần chạy:

| Bộ dữ liệu | DB | correct / total | score/10 | max_time_sec | avg_time_sec |
|---|---|---|---|---|---|
| `tests/test_cases.json` (59 mẫu) | mẫu trong `data/` | 177 / 177 | 10.00 | 0.0025 | 0.0005 |
| `tests/test_cases.json` (59 mẫu) | ~27.000 tên (`benchmark.py`) | 177 / 177 | 10.00 | 0.0095 | 0.0015 |
| 2.000 địa chỉ nhiễu ngẫu nhiên | ~27.000 tên (`benchmark.py`) | 5928 / 6000 | 9.88 | 0.0165 | 0.0010 |

Yêu cầu của đề là max ≤ 0.1 s và trung bình ≤ 0.01 s mỗi request. Khởi tạo (đọc DB + dựng Trie) mất ~0.5 s.
Kết quả trên dữ liệu thật của đề sẽ khác, vì DB và test thật chưa có ở đây.

### Các dạng input đã có test

| Dạng | Ví dụ input |
|---|---|
| Chuẩn | `63 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh` |
| Số nhà có `/` | `69/49/59 Nam Kỳ Khởi Nghĩa, ...` |
| Viết tắt tiền tố | `P. Bến Thành`, `P.Cầu Ông Lãnh`, `TP.HCM`, `X.Cần Giuộc T.Tây Ninh`, `Đ. Võ Văn Tần` |
| Viết tắt tên | `HCM`, `HN`, `ĐN`, `CMT8`, `NKKN`, DB lưu `LTK` |
| Không dấu / HOA | `phuong ben thanh`, `PHƯỜNG BẾN THÀNH` |
| Dính chữ / thiếu dấu phẩy | `NamKỳKhởiNghĩa,PhườngBếnThành`, `XCần Giuộc, TTây Ninh`, `45LêLợi` |
| Lỗi chính tả (OCR) | `Nam Ky Khoi Ngia`, `Bến Thàn`, `Đà Nẵg`, `Ngệ An`, `Minh Khia` |
| Thiếu thành phần | chỉ có tỉnh, chỉ có phường, chuỗi rỗng |
| Không có trong DB | `Lê Lai` không bị sửa thành `Lê Lợi`; `Phường 14` không thành `Phường 1` |
| Trùng tên | `Hai Bà Trưng` (đường / phường), `Bình Thạnh` / `Bình Thành`, `Xã An Phú` / `Phường An Phú` |
| Nhiễu | `Tầng 5, Tòa nhà ABC, ...`, `Giao hàng giờ hành chính - ...`, `..., Việt Nam` |
| Phường số | `P.12`, `Phường 1`, `F1` |

---

## 5. Giới hạn và hướng cải thiện

- **Không dấu nên trùng nhau**: `Hung` có thể là Hùng hoặc Hưng, `Van` là Vân hoặc Văn. Không có dấu thì
  luật không phân biệt được, đang chọn theo thứ tự trong DB.
- **Lỗi ngay ký tự đầu** (`Pường`, `P.ùng Phong`) không được sửa, vì ký tự đầu phải đúng để cắt nhánh nhanh.
- **"Duong" không dấu** đứng đầu tên đường bị hiểu là tiền tố "Đường" (còn "Dương" có dấu thì đúng).
- **Thứ tự** street → ward → province là bắt buộc; địa chỉ viết ngược (tỉnh trước) sẽ sai.
- **Tên cũ trước sáp nhập** (Long An, Bà Rịa - Vũng Tàu, quận/huyện) không có trong DB mới nên không
  được ánh xạ sang tên mới. Có thể thêm một bảng ánh xạ tên cũ → tên mới nếu đề cho phép.
- Nếu DB của đề có quan hệ cha–con (phường thuộc tỉnh nào), có thể thêm điều kiện "phường phải thuộc tỉnh"
  vào bước DP để loại bớt kết quả sai.
- Các trọng số ở đầu `solution.py` (`EDIT_PENALTY`, `BOUNDARY_PENALTY`, ...) nên được tinh chỉnh lại trên
  1.000 mẫu development của đề bằng `evaluate.py --show-errors`.
