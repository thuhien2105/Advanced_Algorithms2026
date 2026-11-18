# -*- coding: utf-8 -*-
"""
Address Segmentation bằng Trie + Quy hoạch động (DP)
=====================================================

Input : một chuỗi địa chỉ (có thể sai chính tả do OCR, viết tắt, thiếu dấu, dính chữ...)
Output: {"street": ..., "ward": ..., "province": ...}; giá trị lấy NGUYÊN VĂN từ DB,
        không tìm thấy thì trả NOT_FOUND.

Thuật toán (chi tiết ở README.md):
  1. Chuẩn hoá : bỏ dấu, viết thường, BỎ khoảng trắng/dấu câu -> chuỗi S,
                 đồng thời ghi lại vị trí ranh giới từ.
  2. Trie      : mỗi loại (street / ward / province) một Trie, khoá là tên đã chuẩn hoá
                 (bỏ tiền tố "Phường", "Tỉnh"...) + tên viết tắt (HCM, NKKN, CMT8...).
                 Một Trie nhỏ nữa cho tiền tố hành chính ("phuong", "p", "xa", "tp", "tinh"...).
  3. Ứng viên  : từ mỗi vị trí i trên S, đi dọc Trie để lấy mọi đoạn S[i:j] khớp một tên.
                 Trường nào vẫn thiếu thì đi Trie kèm bảng Levenshtein (DP trên từng nút Trie)
                 để bắt lỗi chính tả.
  4. DP        : best[j][t] = điểm cao nhất khi đã đọc xong S[:j] và loại cuối cùng đã gán là t,
                 với thứ tự bắt buộc street -> ward -> province. Mỗi bước: bỏ qua 1 ký tự (0 điểm)
                 hoặc nhận 1 ứng viên (điểm ~ số ký tự phủ được - phạt lỗi - phạt lệch ranh giới).
"""
import os
import time
import unicodedata

NOT_FOUND = ""  # slide ghi "Null"; đổi thành "Null" hoặc None nếu bộ chấm yêu cầu

STREET, WARD, PROVINCE = 0, 1, 2
FIELDS = ("street", "ward", "province")
ANY = -1  # tiền tố cấp huyện cũ: đứng trước loại nào cũng được nhưng không được thưởng

# nhóm tiền tố -> các cách viết. Giữ dấu để không nhầm "Dương" (họ) với "Đường",
# "Phương" (tên) với "Phường"; input không dấu thì so không dấu.
PREFIXES = {
    STREET: {"duong": ("đường", "đ", "d"), "pho": ("phố",), "dailo": ("đại lộ",)},
    WARD: {"phuong": ("phường", "p", "f"), "xa": ("xã", "x"),
           "thitran": ("thị trấn", "tt"), "dackhu": ("đặc khu", "đk", "dk")},
    PROVINCE: {"thanhpho": ("thành phố", "tp"), "tinh": ("tỉnh", "t")},
    ANY: {"": ("quận", "q", "huyện", "h", "thị xã", "tx")},
}

# Tham số chấm điểm một ứng viên
EDIT_PENALTY = 2.5             # mỗi lỗi (thêm / xoá / sửa 1 ký tự)
BOUNDARY_PENALTY = 1.5         # đầu hoặc cuối ứng viên rơi vào giữa một từ
PREFIX_BONUS = 1.0             # có tiền tố đúng loại ("Phường" đứng trước tên phường)
ACRONYM_PENALTY = 1.0          # input "Lý Thường Kiệt" khớp với "LTK" trong DB
HOUSE_NUMBER_BONUS = 2.0       # tên đường đứng ngay sau số nhà ("45 Lê Lợi")
TYPE_BIAS = (0.01, 0.02, 0.0)  # phá thế hoà: một tên vừa là đường vừa là phường -> chọn phường
MAX_EDITS = 2
FUZZY_TIME_BUDGET = 0.04       # giây cho lượt tìm gần đúng, để input rất dài vẫn dưới 0.1 s / request
REQUEST_TIME_BUDGET = 0.06     # hạn chót lượt 2, tính từ ĐẦU request (máy chậm thì lượt 1 lâu hơn, lượt 2 ngắn lại)

# Sửa lỗi NGAY KÝ TỰ ĐẦU ("Kguyễn Huệ", "guyễn Huệ", "XNguyễn Huệ")
HEAD_FIX = True
HEAD_ANCHOR = 4                # sau ký tự đầu sai, ANCHOR ký tự kế phải khớp chính xác, lệch là bỏ nhánh
HEAD_MIN_LEN = 10              # chỉ sửa ký tự đầu cho tên dài (tên ngắn đổi chữ đầu dễ ra tên khác có thật)
HEAD_DEL_MIN_LEN = 6           # riêng kiểu MẤT chữ đầu ("uân Trúc" -> Xuân Trúc) cho tên ngắn hơn
HEAD_PENALTY = 1.0             # phạt thêm ngoài EDIT_PENALTY: lỗi ký tự đầu ít gặp hơn lỗi giữa từ
HEAD_DEL_PENALTY = 0.0         # như trên, cho kiểu mất chữ đầu

# Tiền tố viết sai 1 lỗi ("piuong", "Phưường", "Puong", "Thàn phố")
FUZZY_PREFIX_MIN_LEN = 6       # chỉ các tiền tố dài: phuong, thanhpho, thitran, dackhu
FUZZY_PREFIX_PENALTY = 1.5     # thay cho PREFIX_BONUS

# Tên khớp gần đúng BAO TRỌN một tên khớp chính xác ngắn hơn ("Trịnh Đức ân" ⊃ "Trịnh Đức")
CONTAIN_BONUS = 0.5            # tên dài được đẩy lên trên tên ngắn đúng bằng chừng này
ACCENT_BONUS = 0.3             # tỉ lệ dấu của input khớp dấu của tên DB ("Kháh Văn" -> Khánh Văn, không phải Khải Vân)
GROUP_BONUS = 0.3              # tiền tố input cùng nhóm với tên DB ("Xã ..." -> tên "Xã ...")

# Khớp theo từ: 1 từ sai hẳn ("Mkkyễn Thị Minh Khai"), các từ còn lại khớp chính xác
HOLE_MIN_WORDS = 4             # tên DB phải có >= 4 từ (>= 3 từ khớp chính xác)
HOLE_MAX_WORDS = 6
HOLE_LEN_DIFF = 2              # độ dài từ sai lệch tối đa so với từ gốc
HOLE_PENALTY = 2.0             # phạt thêm; ký tự của từ sai cũng không được tính điểm phủ


def _allowed_edits(length):
    """Số lỗi tối đa chấp nhận cho một khoá dài `length` ký tự."""
    if length <= 5:
        return 0
    return 1 if length <= 10 else 2


def _prefix_budget(depth):
    """Cắt nhánh khi duyệt Trie: ký tự đầu phải đúng, tối đa 1 lỗi trong 6 ký tự đầu."""
    if depth <= 1:
        return 0
    return 1 if depth <= 6 else 2


_FOLD = {}


def _fold(ch):
    """'Ệ' -> ('e', 'ệ'), 'Đ' -> ('d', 'đ'); ký tự phân cách -> ('', ...)."""
    r = _FOLD.get(ch)
    if r is None:
        low = ch.lower()[:1]
        base = "d" if low == "đ" else unicodedata.normalize("NFD", low)[0]
        if not ((base.isascii() and base.isalnum()) or base == "/"):
            base = ""
        r = _FOLD[ch] = (base, low)
    return r


def analyze(text):
    """Chuẩn hoá chuỗi.

    Trả về (S, A, O, bound, tokens):
      S      chuỗi không dấu, viết thường, không có khoảng trắng / dấu câu
      A      giống S nhưng còn dấu (để phân biệt "Thạnh" / "Thành")
      O      ký tự gốc (giữ hoa / thường)
      bound  bound[i] = 1 nếu giữa S[i-1] và S[i] có ranh giới từ (kể cả i = 0 và i = len(S))
      tokens danh sách (đầu, cuối) của từng từ trên S. Ngoài dấu cách / dấu câu, còn tách từ
             khi đổi giữa chữ và số ("45LêLợi") hoặc chữ thường -> chữ hoa ("ThuanThanh").
    """
    S, A, O, tokens = [], [], [], []
    start = -1
    prev_kind, prev_lower = 0, False
    for ch in unicodedata.normalize("NFC", text):
        base, low = _fold(ch)
        if not base:
            if start >= 0:
                tokens.append((start, len(S)))
                start = -1
            continue
        kind = 1 if (base.isdigit() or base == "/") else 2
        if start >= 0 and (kind != prev_kind or (prev_lower and ch.isupper())):
            tokens.append((start, len(S)))
            start = -1
        if start < 0:
            start = len(S)
        S.append(base)
        A.append(low)
        O.append(ch)
        prev_kind, prev_lower = kind, ch.islower()
    if start >= 0:
        tokens.append((start, len(S)))
    bound = bytearray(len(S) + 1)
    for a, b in tokens:
        bound[a] = bound[b] = 1
    return "".join(S), "".join(A), "".join(O), bound, tokens


def _initials(words):
    """["cach", "mang", "thang", "8"] -> "cmt8" (từ là số thì giữ nguyên)."""
    return "".join(w if w[0].isdigit() else w[0] for w in words)


def _hole_key(words, h):
    """["nguyen", "thi", "minh", "khai"], 0 -> "0|thi|minh|khai" (từ thứ h bị thay bằng lỗ)."""
    return "%d|%s" % (h, "|".join(words[:h] + words[h + 1:]))


def _same_word(plain, acc, want_plain, want_acc):
    """So một từ với tiền tố: từ có dấu thì phải đúng dấu, từ không dấu thì so không dấu."""
    return acc == want_acc if acc != plain else plain == want_plain


def _prefix_rows():
    """[(loại, nhóm, các từ không dấu, các từ có dấu)] cho mọi cách viết trong PREFIXES."""
    rows = []
    for etype, groups in PREFIXES.items():
        for group, variants in groups.items():
            for v in variants:
                S, A, _, _, toks = analyze(v)
                rows.append((etype, group, tuple(S[a:b] for a, b in toks), tuple(A[a:b] for a, b in toks)))
    return rows


class Trie:
    """Trie dạng dict lồng nhau. Khoá None của mỗi nút chứa danh sách id của tên kết thúc tại đó."""

    __slots__ = ("root", "depth")

    def __init__(self):
        self.root = {}
        self.depth = 0

    def insert(self, key, value):
        node = self.root
        for ch in key:
            nxt = node.get(ch)
            if nxt is None:
                nxt = node[ch] = {}
            node = nxt
        values = node.get(None)
        if values is None:
            values = node[None] = []
        if value not in values:
            values.append(value)
        self.depth = max(self.depth, len(key))

    def exact(self, s, start, end):
        """Mọi (j, ids, 0) sao cho s[start:j] là một khoá, j <= end. O(độ dài khoá dài nhất)."""
        out = []
        node = self.root
        for j in range(start, end):
            node = node.get(s[j])
            if node is None:
                break
            values = node.get(None)
            if values is not None:
                out.append((j + 1, values, 0))
        return out

    def fuzzy(self, s, start, end):
        """Mọi (j, ids, d) với d = Levenshtein(s[start:j], khoá) <= _allowed_edits(len(khoá)).

        Duyệt DFS trên Trie, mỗi nút giữ một hàng của bảng DP Levenshtein; hàng của nút con
        tính từ hàng của nút cha nên các khoá chung tiền tố dùng chung phép tính.
        Chỉ tính trong dải |x - depth| <= MAX_EDITS và cắt nhánh theo _prefix_budget.
        Bỏ qua khoá chứa chữ số: số phường / số đường phải khớp chính xác.
        """
        L = min(end - start, self.depth + MAX_EDITS)
        if L <= 0:
            return []
        INF = MAX_EDITS + 1
        stack = [(self.root, [x if x <= MAX_EDITS else INF for x in range(L + 1)], 0)]
        return self._dfs(s[start:start + L], L, start, stack, 0)

    def fuzzy_head(self, s, start, end):
        """Như fuzzy() nhưng cho phép ký tự ĐẦU sai (đúng 1 lỗi ở đó), không phải duyệt Levenshtein cả Trie.

        Quét MỌI nhánh con của gốc, nhưng mỗi nhánh chỉ đi tiếp HEAD_ANCHOR bước bằng tra dict
        (khớp chính xác). Lệch ở bước nào thì bỏ nhánh đó, sang nhánh kế. Nhánh nào qua được
        đoạn neo mới chạy tiếp DFS Levenshtein như fuzzy(). Ba kiểu lỗi ký tự đầu:
          sửa : input "Kguyen..."  -> nhánh c != s[0], neo theo s[1:]
          thiếu: input "guyen..."  -> nhánh c bất kỳ,  neo theo s[0:]
          thừa : input "Xnguyen..." -> đi từ gốc,      neo theo s[1:]
        Chỉ trả khoá dài >= HEAD_MIN_LEN (kiểu "thiếu": >= HEAD_DEL_MIN_LEN).
        """
        L = min(end - start, self.depth + MAX_EDITS)
        if L <= HEAD_ANCHOR + 1 or not s[start].isalpha():
            return []
        seg = s[start:start + L]
        INF = MAX_EDITS + 1
        stack, stack_del = [], []

        def anchor(node, used, depth, stack=stack):
            # đi chính xác HEAD_ANCHOR ký tự seg[used:used+HEAD_ANCHOR] từ `node`
            for x in range(used, used + HEAD_ANCHOR):
                node = node.get(seg[x])
                if node is None:
                    return
            used += HEAD_ANCHOR
            depth += HEAD_ANCHOR
            # hàng DP: chỉ các cách gióng đi qua điểm neo (1 lỗi ở ký tự đầu)
            row = [min(INF, 1 + abs(x - used)) for x in range(L + 1)]
            stack.append((node, row, depth))

        first = seg[0]
        for c, child in self.root.items():
            if c is None or not c.isalpha():
                continue
            if c != first:
                anchor(child, 1, 1)          # sửa ký tự đầu
            anchor(child, 0, 1, stack_del)   # input thiếu ký tự đầu
        anchor(self.root, 1, 0)              # input thừa ký tự đầu
        return ([m + (HEAD_PENALTY,) for m in self._dfs(seg, L, start, stack, HEAD_MIN_LEN)]
                + [m + (HEAD_DEL_PENALTY,) for m in self._dfs(seg, L, start, stack_del, HEAD_DEL_MIN_LEN)])

    def _dfs(self, seg, L, start, stack, min_len):
        """DFS Levenshtein dùng chung cho fuzzy() và fuzzy_head()."""
        INF = MAX_EDITS + 1
        out = []
        while stack:
            node, prev, depth = stack.pop()
            d = depth + 1
            lo, hi = max(1, d - MAX_EDITS), min(L, d + MAX_EDITS)
            if lo > hi:
                continue
            budget = _prefix_budget(d)
            for ch, child in node.items():
                if ch is None or ch.isdigit():
                    continue
                row = [INF] * (L + 1)
                if d <= MAX_EDITS:
                    row[0] = d
                best = row[0]
                for x in range(lo, hi + 1):
                    v = prev[x - 1] + (seg[x - 1] != ch)   # khớp / sửa
                    w = prev[x] + 1                        # khoá thừa 1 ký tự
                    if w < v:
                        v = w
                    w = row[x - 1] + 1                     # input thừa 1 ký tự
                    if w < v:
                        v = w
                    if v > INF:
                        v = INF
                    row[x] = v
                    if v < best:
                        best = v
                if best > budget:
                    continue
                values = child.get(None)
                if values is not None and d >= min_len:
                    allowed = _allowed_edits(d)
                    for x in range(lo, hi + 1):
                        if row[x] <= allowed:
                            out.append((start + x, values, row[x]))
                stack.append((child, row, d))
        return out


def _best_segmentation(n, units):
    """DP chọn tập ứng viên không chồng nhau, đúng thứ tự street -> ward -> province, tổng điểm lớn nhất.

    units: các bộ (i, j, loại, điểm, id) – ứng viên phủ S[i:j].
    best[p][st]: điểm tốt nhất sau khi đọc S[:p], st = 0 (chưa gán gì) hoặc 1 + loại vừa gán.
    Độ phức tạp O(4n + 4·|units|).
    """
    NEG = float("-inf")
    by_start = [[] for _ in range(n + 1)]
    for u in units:
        by_start[u[0]].append(u)
    best = [[NEG] * 4 for _ in range(n + 1)]
    back = [[None] * 4 for _ in range(n + 1)]
    best[0][0] = 0.0
    for p in range(n + 1):
        cur = best[p]
        if p < n:  # bỏ qua ký tự S[p]
            nxt, nback = best[p + 1], back[p + 1]
            for st in range(4):
                if cur[st] > nxt[st]:
                    nxt[st] = cur[st]
                    nback[st] = (p, st, None)
        for u in by_start[p]:  # nhận ứng viên bắt đầu tại p
            j, ns, score = u[1], u[2] + 1, u[3]
            tgt, tback = best[j], back[j]
            for st in range(ns):
                v = cur[st] + score
                if v > tgt[ns]:
                    tgt[ns] = v
                    tback[ns] = (p, st, u)
    st = max(range(4), key=lambda x: best[n][x])
    chosen, p = {}, n
    while p > 0:
        p, st, u = back[p][st]
        if u is not None:
            chosen[u[2]] = u
    return chosen


def _promote_containing(units, n_exact, n, bound):
    """Ứng viên gần đúng F (lượt 2) bao trọn một ứng viên khớp chính xác E ngắn hơn, cùng loại,
    và F kết thúc đúng ranh giới từ -> F được ít nhất điểm(E) + CONTAIN_BONUS.

    "Trịnh Đức ân": E = "Trịnh Đức" (khớp đúng, bỏ thừa "ân") thua F = "Trịnh Đức Vân" (1 lỗi).
    DP vẫn quyết định cuối cùng: nếu phần thừa là một trường khác ("Trịnh Đức, An Phú")
    thì E + phường vẫn hơn F.
    """
    exact_at = [[] for _ in range(n + 1)]
    for u in units[:n_exact]:
        exact_at[u[0]].append(u)
    out = units[:n_exact]
    for f in units[n_exact:]:
        fi, fj, ft, fs0 = f[0], f[1], f[2], f[3]
        fs = fs0
        if bound[fj]:
            for p in range(fi, fj):
                for e in exact_at[p]:
                    if e[2] != ft or e[4] == f[4] or e[1] > fj or e[1] - e[0] >= fj - fi:
                        continue  # khác loại / cùng một tên (chỉ là E kéo dài thêm lỗi) / không bao trọn
                    # lên trên E, nhưng giữ thứ tự điểm gốc giữa các F cùng bao E
                    v = e[3] + max(0.05, CONTAIN_BONUS + 0.05 * (fs0 - e[3]))
                    if v > fs:
                        fs = v
        out.append(f if fs == fs0 else (fi, fj, ft, fs, f[4]))
    return out


class Solution:
    def __init__(self, province_path=None, ward_path=None, street_path=None):
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        self.province_path = province_path or os.path.join(data_dir, "list_province.txt")
        self.ward_path = ward_path or os.path.join(data_dir, "list_ward.txt")
        self.street_path = street_path or os.path.join(data_dir, "list_street.txt")

        self.names = []                 # id -> tên gốc trong DB (giá trị trả về)
        self.groups = []                # id -> nhóm tiền tố của tên trong DB ("phuong", "xa"...) hoặc None
        self.accents = []               # id -> phần tên chính: có dấu, viết thường, không khoảng trắng
        self.tries = (Trie(), Trie(), Trie())
        self.initials = (Trie(), Trie(), Trie())  # chữ cái đầu của tên DB: "nkkn", "cmt8", "hcm"
        self.acronyms = ({}, {}, {})    # tên viết tắt trong DB ("LTK") -> so với chữ cái đầu của input
        self.holes = {}                 # "thi|minh|khai" + vị trí lỗ -> [(loại, id, độ dài từ gốc)]
        self.db_words = set()           # mọi từ (không dấu) xuất hiện trong tên DB
        self._ids = {}

        self.prefix_rows = _prefix_rows()
        self.prefixes = Trie()   # khoá không dấu, giá trị (loại, nhóm, dạng có dấu)
        for etype, group, plain, acc in self.prefix_rows:
            self.prefixes.insert("".join(plain), (etype, group, "".join(acc)))
        self.prefix_words = {w for _, _, plain, _ in self.prefix_rows for w in plain}

        for etype, path in ((STREET, self.street_path), (WARD, self.ward_path),
                            (PROVINCE, self.province_path)):
            with open(path, encoding="utf-8-sig") as f:
                for line in f:
                    name = line.strip()
                    if name and not name.startswith("#"):
                        self._add(etype, name)
        self.fuzzy_prefixes = self._build_fuzzy_prefixes()

    def _build_fuzzy_prefixes(self):
        """Mọi cách viết sai 1 lỗi (thêm / xoá / sửa / đảo, không đụng ký tự đầu) của các tiền tố dài.
        Bỏ cách viết trùng một từ có trong DB ("phung" ~ "phuong" nhưng Phùng là họ) hoặc trùng tiền tố khác."""
        letters = "abcdefghijklmnopqrstuvwxyz"
        exact = {"".join(plain) for _, _, plain, _ in self.prefix_rows}
        trie = Trie()
        for etype, group, plain, acc in self.prefix_rows:
            word = "".join(plain)
            if etype == ANY or len(word) < FUZZY_PREFIX_MIN_LEN:
                continue
            variants = set()
            for p in range(1, len(word) + 1):
                variants.add(word[:p] + word[p + 1:])                          # xoá
                for c in letters:
                    variants.add(word[:p] + c + word[p:])                      # thêm
                    variants.add(word[:p] + c + word[p + 1:])                  # sửa
                if p + 1 < len(word):
                    variants.add(word[:p] + word[p + 1] + word[p] + word[p + 2:])  # đảo
            for v in variants:
                if len(v) >= 4 and v not in exact and v not in self.db_words:
                    trie.insert(v, (etype, group, "".join(acc)))
        return trie

    # ------------------------------------------------------------------ dựng Trie
    def _add(self, etype, name):
        if (etype, name) in self._ids:
            return
        S, A, O, _, toks = analyze(name)
        if not toks:
            return
        words = [S[a:b] for a, b in toks]
        group, skip = self._split_prefix(etype, words, [A[a:b] for a, b in toks])
        core, core_words = toks[skip:], words[skip:]
        c0, c1 = core[0][0], core[-1][1]
        key = S[c0:c1]

        eid = len(self.names)
        self._ids[(etype, name)] = eid
        self.names.append(name)
        self.groups.append(group)
        self.accents.append(A[c0:c1])
        self.db_words.update(words)
        trie = self.tries[etype]
        if HOLE_MIN_WORDS <= len(core_words) <= HOLE_MAX_WORDS:
            for h, w in enumerate(core_words):
                if w.isalpha():
                    self.holes.setdefault(_hole_key(core_words, h), []).append((etype, eid, len(w)))

        if etype != STREET and (len(key) <= 2 or not any(c.isalpha() for c in key)):
            # "Phường 1", "Phường 12": tên quá ngắn / toàn số -> bắt buộc đi kèm tiền tố ("p1", "f12"...)
            for pt, g, plain, _ in self.prefix_rows:
                if pt == etype and (group is None or g == group):
                    trie.insert("".join(plain) + key, eid)
            return

        trie.insert(key, eid)
        if len(core_words) >= 3 or (etype == PROVINCE and group == "thanhpho" and len(core_words) == 2):
            self.initials[etype].insert(_initials(core_words), eid)   # "hcm", "hn", "nkkn", "cmt8"
        contiguous = all(core[k][1] == core[k + 1][0] for k in range(len(core) - 1))
        if contiguous and O[c0:c1].isupper() and 2 <= c1 - c0 <= 8:
            self.acronyms[etype].setdefault(key, []).append(eid)   # DB lưu "LTK", "CMT8"

    def _split_prefix(self, etype, words, accs):
        """["phuong", "ben", "thanh"] -> ("phuong", 1); chỉ cắt khi còn lại ít nhất 1 từ.
        "Dương Minh" không bị cắt vì "dương" khác dấu với "đường"."""
        best_group, best_len = None, 0
        for pt, group, plain, acc in self.prefix_rows:
            m = len(plain)
            if pt == etype and best_len < m < len(words) and all(
                    _same_word(words[x], accs[x], plain[x], acc[x]) for x in range(m)):
                best_group, best_len = group, m
        return best_group, best_len

    # ------------------------------------------------------------------ xử lý 1 request
    def process(self, s):
        t_start = time.perf_counter()
        result = {f: NOT_FOUND for f in FIELDS}
        S, A, O, bound, tokens = analyze(s or "")
        n = len(S)
        if n == 0:
            return result
        ctx = (S, A, O, bound)

        # Lượt 1: chỉ khớp chính xác (rất nhanh)
        units = []
        for i in range(n):
            self._collect(ctx, i, n, (STREET, WARD, PROVINCE), False, units)
        self._collect_acronyms(S, tokens, units)
        chosen = _best_segmentation(n, units)

        # Lượt 2: còn chữ cái nào chưa được giải thích thì tìm gần đúng (Levenshtein trên Trie)
        # từ mọi đầu từ. Chạy cả khi lượt 1 đã đủ 3 trường, vì lượt 1 có thể chỉ khớp được một tên
        # ngắn hơn ("Nam Kỳ" thay vì "Nam Ky Khoi Ngia") hoặc khớp nhầm.
        # Duyệt từ cuối chuỗi (tỉnh/phường thường nằm cuối) và dừng khi hết FUZZY_TIME_BUDGET:
        # chỉ input rất dài (kèm ghi chú hàng trăm ký tự) mới chạm giới hạn này.
        covered = bytearray(n)
        for u in chosen.values():
            covered[u[0]:u[1]] = b"\x01" * (u[1] - u[0])
        if any(S[p].isalpha() and not covered[p] for p in range(n)):
            deadline = min(time.perf_counter() + FUZZY_TIME_BUDGET, t_start + REQUEST_TIME_BUDGET)
            n_exact = len(units)
            self._collect_holes(ctx, tokens, covered, deadline, units)
            for i in range(n - 1, -1, -1):
                if bound[i]:
                    self._collect(ctx, i, n, (STREET, WARD, PROVINCE), True, units)
                    if time.perf_counter() > deadline:
                        break
            units = _promote_containing(units, n_exact, n, bound)
            chosen = _best_segmentation(n, units)

        for t, u in chosen.items():
            result[FIELDS[t]] = self.names[u[4]]
        return result

    def _collect(self, ctx, i, end, types, fuzzy, out):
        """Sinh ứng viên bắt đầu tại i; tên có thể đi sau một tiền tố hành chính ("P.", "Tỉnh"...)."""
        S, A, O, bound = ctx
        starts = [(i, None, PREFIX_BONUS)]
        keyword = False  # từ tại i là nguyên một tiền tố ("phuong", "tp", "quan"...)
        for k, infos, _ in self.prefixes.exact(S, i, end):
            acc = A[i:k]
            if acc != S[i:k]:  # input có dấu: cho sai 1 dấu ("Phuờng"), nhưng "Dương" (2 dấu) ≠ "Đường"
                infos = [x for x in infos if sum(a != b for a, b in zip(acc, x[2])) <= 1]
            if k < end and infos:
                starts.append((k, infos, PREFIX_BONUS))
                keyword = keyword or bool(bound[k])
        if bound[i]:
            # tiền tố viết sai 1 lỗi: phải đứng thành từ riêng, và dấu của input (nếu có) phải là dấu
            # của tiền tố ("Phưường" được, "Phùng" không)
            for k, infos, _ in self.fuzzy_prefixes.exact(S, i, end):
                if k < end and bound[k]:
                    marks = [c for c in A[i:k] if c > "\x7f"]
                    infos = [x for x in infos if all(c in x[2] for c in marks)]
                    if infos:
                        starts.append((k, infos, -FUZZY_PREFIX_PENALTY))
                        keyword = True
        for k, infos, prefix_bonus in starts:
            if fuzzy and k == i and keyword:
                continue  # không sửa lỗi "phuong" thành tên "Phú Long"
            for t in types:
                group, bonus = None, 0.0
                if infos is not None:
                    ok = False
                    for pt, g, _ in infos:
                        if pt == t:
                            ok, group, bonus = True, g, prefix_bonus
                            break
                        if pt == ANY:
                            ok = True
                    if not ok:
                        continue
                trie = self.tries[t]
                if fuzzy:
                    matches = trie.fuzzy(S, k, end)
                    if HEAD_FIX:
                        for j, ids, edits, penalty in trie.fuzzy_head(S, k, end):
                            unit = self._score(ctx, i, k, j, t, ids, edits, group, bonus)
                            if unit is not None and unit[3] - penalty >= max(2.0, 0.5 * (j - i)):
                                out.append(unit[:3] + (unit[3] - penalty,) + unit[4:])
                else:
                    matches = trie.exact(S, k, end)
                    for m in self.initials[t].exact(S, k, end):
                        # viết tắt đường/phường phải viết HOA ("NKKN"), để "khu" không thành "Kiều Hòa Uyên"
                        if t == PROVINCE or O[k:m[0]].isupper():
                            matches.append(m)
                for j, ids, edits in matches:
                    if fuzzy and not edits:
                        continue  # khớp chính xác đã có từ lượt 1
                    unit = self._score(ctx, i, k, j, t, ids, edits, group, bonus)
                    if unit is not None:
                        out.append(unit)

    def _score(self, ctx, i, k, j, t, ids, edits, group, bonus):
        """Điểm của ứng viên S[i:j] (tiền tố S[i:k] + tên S[k:j]); None nếu không hợp lệ."""
        S, A, _, bound = ctx
        if j - k <= 3 and not (bound[j] and (k > i or bound[i])):
            return None  # tên rất ngắn ("hcm", "hue", "p1") phải đứng thành từ riêng
        if not bound[j] and S[j - 1].isdigit() and S[j].isdigit():
            return None  # "p1" không được khớp vào "p14"
        if not bound[k] and S[k].isdigit() and S[k - 1].isdigit():
            return None
        if edits and any(c.isdigit() for c in S[k:j]):
            return None  # không sửa lỗi trên phần chữ số
        covered = j - i
        score = covered - EDIT_PENALTY * edits + bonus + TYPE_BIAS[t]
        if not bound[i]:
            score -= BOUNDARY_PENALTY
        if not bound[j]:
            score -= BOUNDARY_PENALTY
        if score < max(2.0, 0.5 * covered):
            return None
        if t == STREET and i > 0 and S[i - 1].isdigit():
            score += HOUSE_NUMBER_BONUS
        eid = self._pick(ids, group, A[k:j])
        if group is not None and self.groups[eid] == group:
            score += GROUP_BONUS
        marks = [c for c in A[k:j] if c > "\x7f"]
        if marks:
            ref = self.accents[eid]
            score += ACCENT_BONUS * sum(c in ref for c in marks) / len(marks)
        return (i, j, t, score, eid)

    def _pick(self, ids, group, accented):
        """Nhiều tên cùng khoá không dấu (vd "Phường Bình Thạnh" / "Xã Bình Thành"):
        ưu tiên tên cùng nhóm tiền tố với input, rồi đến tên giống dấu nhất."""
        if len(ids) == 1:
            return ids[0]

        marks = [c for c in accented if c > "\x7f"]

        def rank(e):
            ref = self.accents[e]
            same = sum(a == b for a, b in zip(ref, accented)) if len(ref) == len(accented) else 0
            # input có lỗi nên độ dài lệch ("kháhvăn" / "khánhvăn"): so tập dấu
            hit = sum(c in ref for c in marks)
            return (group is not None and self.groups[e] == group, same, hit)

        return max(ids, key=rank)

    def _collect_holes(self, ctx, tokens, covered, deadline, out):
        """Tên DB >= HOLE_MIN_WORDS từ, input sai hẳn 1 từ ("Mkkyễn Thị Minh Khai"), các từ khác đúng.

        Mỗi cửa sổ m từ liên tiếp của input, mỗi vị trí lỗ h: tra bảng self.holes (1 phép tra dict).
        Chỉ nhận khi đúng 1 tên DB khớp (nhiều tên -> không đoán), từ ở lỗ chưa được phủ ở lượt 1,
        dài gần bằng từ gốc và không phải một tiền tố ("phuong" không được làm lỗ).
        """
        S = ctx[0]
        words = [S[a:b] for a, b in tokens]
        known = [w in self.db_words for w in words]
        for a in range(len(words)):
            if time.perf_counter() > deadline:
                return
            for m in range(HOLE_MIN_WORDS, min(HOLE_MAX_WORDS, len(words) - a) + 1):
                window = words[a:a + m]
                misses = m - sum(known[a:a + m])
                if misses > 1:
                    break  # cửa sổ dài hơn cũng sẽ có >= 2 từ lạ
                for h in range(m):
                    if misses == 1 and known[a + h]:
                        continue  # đã có 1 từ lạ thì lỗ phải nằm đúng ở đó
                    w = window[h]
                    ws, we = tokens[a + h]
                    if not w.isalpha() or w in self.prefix_words or covered[ws]:
                        continue
                    hits = [x for x in self.holes.get(_hole_key(window, h), ())
                            if abs(x[2] - len(w)) <= HOLE_LEN_DIFF]
                    if len({x[1] for x in hits}) != 1:
                        continue
                    t, eid, _ = hits[0]
                    i, j = tokens[a][0], tokens[a + m - 1][1]
                    unit = self._score(ctx, i, i, j, t, [eid], 0, None, 0.0)
                    if unit is None:
                        continue
                    score = unit[3] - (we - ws) - HOLE_PENALTY
                    if score >= max(2.0, 0.5 * (j - i - (we - ws))):
                        out.append(unit[:3] + (score,) + unit[4:])

    def _collect_acronyms(self, S, tokens, out):
        """Input viết đầy đủ ("Lý Thường Kiệt") nhưng DB lưu viết tắt ("LTK")."""
        if not any(self.acronyms):
            return
        words = [S[a:b] for a, b in tokens]
        for a in range(len(words)):
            for b in range(a + 2, min(len(words), a + 8) + 1):
                key = _initials(words[a:b])
                for t in (STREET, WARD, PROVINCE):
                    ids = self.acronyms[t].get(key)
                    if ids:
                        i, j = tokens[a][0], tokens[b - 1][1]
                        out.append((i, j, t, (j - i) - ACRONYM_PENALTY + TYPE_BIAS[t], ids[0]))
