# %% cell 1
# Change your team name to Group_xx
TEAM_NAME = 'Group_8'

# %% cell 2
# NOTE: you CAN change this cell
# If you want to use your own database, download it here
# Không dùng DB riêng: chỉ dùng list_province / list_ward / list_street truyền vào Solution

# %% cell 3
# NOTE: you CAN change this cell
# Add more to your needs
# you must place ALL pip install here
# Không cần cài thêm: lời giải chỉ dùng thư viện chuẩn của Python

# %% cell 4
# NOTE: you CAN change this cell
# import your library here
import os
import time
import unicodedata

# %% cell 5
# NOTE: you MUST change this cell
# New methods / functions must be written under class Solution.
class Solution:

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
    SHORT_NAME_LEN = 5             # tên <= 5 ký tự được sửa 1 lỗi, nhưng phải khớp dấu nếu input có dấu
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

    # Thứ tự các trường: không bắt buộc, chỉ thưởng khi đúng thứ tự street -> ward -> province
    ORDER_BONUS = 0.3

    # Khớp LỎNG (lượt 3, chỉ trên phần input chưa được giải thích): sai / thiếu ký tự tới 40% tên,
    # nhưng TỪ ĐẦU của tên phải sai < 60% (sai 60-80% thì bỏ, xét ứng viên khác)
    LOOSE_MAX_RATIO = 0.4
    FIRST_WORD_MAX_RATIO = 0.6     # ngưỡng loại (không tính dấu bằng): lỗi / độ dài từ đầu < 0.6
    LOOSE_EDIT_PENALTY = 1.0       # mỗi lỗi; nhẹ hơn EDIT_PENALTY vì chỉ chạy ở chỗ chưa có gì khớp
    LOOSE_PENALTY = 1.0
    LOOSE_MIN_SCORE = 1.0
    LOOSE_TOP = 15                 # số ứng viên (xếp theo bigram chung) được kiểm tra Levenshtein mỗi vị trí
    LOOSE_MIN_LEN = 5              # tên ngắn hơn: 40% chỉ còn 1 lỗi, lượt 2 đã lo

    # Từ viết tắt (không dấu, đã bỏ dấu chấm) -> các từ đầy đủ có thể có, theo thứ tự hay gặp.
    # Viết tắt mất > 60% ký tự ("Ng" / "Nguyễn" mất 4/6) nên không qua được ngưỡng từ đầu: tra bảng này,
    # thử MỌI giá trị, phần còn lại của tên vẫn phải sai <= 40%, lấy tên gần nhất (ít lỗi nhất).
    ABBREVIATIONS = {
        "ng": ("nguyen", "ngo", "nghiem"),
        "ngg": ("nguyen",),
        "nguy": ("nguyen",),
        "tr": ("tran", "truong", "trinh", "trieu"),
        "ph": ("pham", "phan", "phung", "phuong"),
        "hg": ("hoang", "hung", "huong"),
        "hng": ("hoang", "hung"),
        "lg": ("luong", "long"),
        "vg": ("vuong",),
        "dg": ("duong", "dang"),
        "qg": ("quang",),
        "thg": ("thuong", "thang"),
        "tg": ("tuong", "trung"),
        "bh": ("binh",),
        "kh": ("khanh", "khai"),
    }
    ABBREV_ORDER_PENALTY = 0.01    # cùng số lỗi: ưu tiên giá trị đứng trước trong bảng
    ABBREV_COST = 0.3              # mỗi từ viết tắt ở giữa tên ("T" -> Thị): nhẹ hơn 1 lỗi ký tự


    @staticmethod
    def _allowed_edits(length):
        """Số lỗi tối đa chấp nhận cho một khoá dài `length` ký tự."""
        return 1 if length <= 10 else 2


    @staticmethod
    def _loose_budget(length):
        """Số lỗi tối đa của khớp lỏng cho tên dài `length`: <= 40%."""
        return int(length * Solution.LOOSE_MAX_RATIO)


    @staticmethod
    def _first_word_budget(length):
        """Số lỗi tối đa của từ đầu: lỗi / độ dài < 60% (4 ký tự -> 2, 6 -> 3, 7 -> 4)."""
        return max(0, -(-length * int(Solution.FIRST_WORD_MAX_RATIO * 100) // 100) - 1)   # ceil(60% * length) - 1


    @staticmethod
    def _lev(a, b):
        """Levenshtein 2 chuỗi ngắn."""
        prev = list(range(len(b) + 1))
        for x, ca in enumerate(a, 1):
            cur = [x]
            for y, cb in enumerate(b, 1):
                cur.append(min(prev[y - 1] + (ca != cb), prev[y] + 1, cur[y - 1] + 1))
            prev = cur
        return prev[-1]


    @staticmethod
    def _deletes(word, k):
        """Mọi chuỗi thu được khi xoá tối đa k ký tự của word (kiểu SymSpell)."""
        out, frontier = {word}, {word}
        for _ in range(k):
            frontier = {w[:p] + w[p + 1:] for w in frontier for p in range(len(w))}
            out |= frontier
        return out


    @staticmethod
    def _bigrams(s):
        return frozenset(s[x:x + 2] for x in range(len(s) - 1))


    @staticmethod
    def _anchored_lev(key, S, k, end, bound, budget):
        """min Levenshtein(key, S[k:x]) với k < x <= end và x là ranh giới từ.
        Trả (số lỗi, x) hoặc None nếu > budget. Dừng sớm khi cả hàng DP đã vượt budget."""
        W = end - k
        if W <= 0:
            return None
        prev = list(range(W + 1))
        for r, c in enumerate(key, 1):
            cur = [r] + [0] * W
            low = r
            for x in range(1, W + 1):
                v = prev[x - 1] + (S[k + x - 1] != c)
                w = prev[x] + 1
                if w < v:
                    v = w
                w = cur[x - 1] + 1
                if w < v:
                    v = w
                cur[x] = v
                if v < low:
                    low = v
            if low > budget:
                return None
            prev = cur
        best = None
        L = len(key)
        for x in range(1, W + 1):
            d = prev[x]
            if d <= budget and bound[k + x]:
                cand = (d, abs(x - L), x)
                if best is None or cand < best:
                    best = cand
        return None if best is None else (best[0], k + best[2])


    @staticmethod
    def _prefix_budget(depth):
        """Cắt nhánh khi duyệt Trie: ký tự đầu phải đúng, tối đa 1 lỗi trong 6 ký tự đầu."""
        if depth <= 1:
            return 0
        return 1 if depth <= 6 else 2


    _FOLD = {}


    @staticmethod
    def _fold(ch):
        """'Ệ' -> ('e', 'ệ'), 'Đ' -> ('d', 'đ'); ký tự phân cách -> ('', ...)."""
        r = Solution._FOLD.get(ch)
        if r is None:
            low = ch.lower()[:1]
            base = "d" if low == "đ" else unicodedata.normalize("NFD", low)[0]
            if not ((base.isascii() and base.isalnum()) or base == "/"):
                base = ""
            r = Solution._FOLD[ch] = (base, low)
        return r


    @staticmethod
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
        squash = None
        for ch in unicodedata.normalize("NFC", text):
            base, low = Solution._fold(ch)
            if not base:
                squash = None
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
            if kind == 2:
                # chữ cái lặp >= 3 lần liền trong 1 từ ("khaiiiii", "Bànnnn") là nhiễu: gộp còn 1.
                # Tiếng Việt bỏ dấu không có chữ cái lặp 3 lần; lặp 2 lần để Levenshtein lo.
                if base == squash:
                    continue
                squash = None
                if len(S) - start >= 2 and S[-1] == base and S[-2] == base:
                    S.pop()
                    A.pop()
                    O.pop()
                    squash = base
                    continue
            else:
                squash = None
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


    @staticmethod
    def _initials(words):
        """["cach", "mang", "thang", "8"] -> "cmt8" (từ là số thì giữ nguyên)."""
        return "".join(w if w[0].isdigit() else w[0] for w in words)


    @staticmethod
    def _hole_key(words, h):
        """["nguyen", "thi", "minh", "khai"], 0 -> "0|thi|minh|khai" (từ thứ h bị thay bằng lỗ)."""
        return "%d|%s" % (h, "|".join(words[:h] + words[h + 1:]))


    @staticmethod
    def _same_word(plain, acc, want_plain, want_acc):
        """So một từ với tiền tố: từ có dấu thì phải đúng dấu, từ không dấu thì so không dấu."""
        return acc == want_acc if acc != plain else plain == want_plain


    @staticmethod
    def _prefix_rows():
        """[(loại, nhóm, các từ không dấu, các từ có dấu)] cho mọi cách viết trong PREFIXES."""
        rows = []
        for etype, groups in Solution.PREFIXES.items():
            for group, variants in groups.items():
                for v in variants:
                    S, A, _, _, toks = Solution.analyze(v)
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
            L = min(end - start, self.depth + Solution.MAX_EDITS)
            if L <= 0:
                return []
            INF = Solution.MAX_EDITS + 1
            stack = [(self.root, [x if x <= Solution.MAX_EDITS else INF for x in range(L + 1)], 0)]
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
            L = min(end - start, self.depth + Solution.MAX_EDITS)
            if L <= Solution.HEAD_ANCHOR + 1 or not s[start].isalpha():
                return []
            seg = s[start:start + L]
            INF = Solution.MAX_EDITS + 1
            stack, stack_del = [], []

            def anchor(node, used, depth, stack=stack):
                # đi chính xác HEAD_ANCHOR ký tự seg[used:used+HEAD_ANCHOR] từ `node`
                for x in range(used, used + Solution.HEAD_ANCHOR):
                    node = node.get(seg[x])
                    if node is None:
                        return
                used += Solution.HEAD_ANCHOR
                depth += Solution.HEAD_ANCHOR
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
            return ([m + (Solution.HEAD_PENALTY,) for m in self._dfs(seg, L, start, stack, Solution.HEAD_MIN_LEN)]
                    + [m + (Solution.HEAD_DEL_PENALTY,) for m in self._dfs(seg, L, start, stack_del, Solution.HEAD_DEL_MIN_LEN)])

        def _dfs(self, seg, L, start, stack, min_len):
            """DFS Levenshtein dùng chung cho fuzzy() và fuzzy_head()."""
            INF = Solution.MAX_EDITS + 1
            out = []
            while stack:
                node, prev, depth = stack.pop()
                d = depth + 1
                lo, hi = max(1, d - Solution.MAX_EDITS), min(L, d + Solution.MAX_EDITS)
                if lo > hi:
                    continue
                budget = Solution._prefix_budget(d)
                for ch, child in node.items():
                    if ch is None or ch.isdigit():
                        continue
                    row = [INF] * (L + 1)
                    if d <= Solution.MAX_EDITS:
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
                        allowed = Solution._allowed_edits(d)
                        for x in range(lo, hi + 1):
                            if row[x] <= allowed:
                                out.append((start + x, values, row[x]))
                    stack.append((child, row, d))
            return out


    @staticmethod
    def _best_segmentation(n, units):
        """DP chọn tập ứng viên không chồng nhau, mỗi loại tối đa 1, THỨ TỰ TUỲ Ý, tổng điểm lớn nhất.

        units: các bộ (i, j, loại, điểm, id) – ứng viên phủ S[i:j].
        best[p][st]: điểm tốt nhất sau khi đọc S[:p]; st = mask * 4 + (loại vừa gán + 1),
        mask = tập loại đã gán. Ứng viên đi sau loại có thứ tự nhỏ hơn (street < ward < province)
        được + ORDER_BONUS: thứ tự chuẩn chỉ để phá thế hoà, "TP HCM, P. Bến Thành, 12 Lê Lợi" vẫn đúng.
        Độ phức tạp O(32n + 32·|units|).
        """
        NEG = float("-inf")
        NS = 32
        by_start = [[] for _ in range(n + 1)]
        for u in units:
            by_start[u[0]].append(u)
        best = [[NEG] * NS for _ in range(n + 1)]
        back = [[None] * NS for _ in range(n + 1)]
        best[0][0] = 0.0
        for p in range(n + 1):
            cur = best[p]
            live = [st for st in range(NS) if cur[st] != NEG]
            if p < n:  # bỏ qua ký tự S[p]
                nxt, nback = best[p + 1], back[p + 1]
                for st in live:
                    if cur[st] > nxt[st]:
                        nxt[st] = cur[st]
                        nback[st] = (p, st, None)
            for u in by_start[p]:  # nhận ứng viên bắt đầu tại p
                j, t, score = u[1], u[2], u[3]
                bit = 1 << t
                tgt, tback = best[j], back[j]
                for st in live:
                    mask = st >> 2
                    if mask & bit:
                        continue
                    v = cur[st] + score + (Solution.ORDER_BONUS if t > (st & 3) - 1 else 0.0)
                    ns = ((mask | bit) << 2) | (t + 1)
                    if v > tgt[ns]:
                        tgt[ns] = v
                        tback[ns] = (p, st, u)
        st = max(range(NS), key=lambda x: best[n][x])
        chosen, p = {}, n
        while p > 0:
            p, st, u = back[p][st]
            if u is not None:
                chosen[u[2]] = u
        return chosen


    @staticmethod
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
                        v = e[3] + max(0.05, Solution.CONTAIN_BONUS + 0.05 * (fs0 - e[3]))
                        if v > fs:
                            fs = v
            out.append(f if fs == fs0 else (fi, fj, ft, fs, f[4]))
        return out


    def __init__(self, list_province=None, list_ward=None, list_street=None,
                 province_path=None, ward_path=None, street_path=None):
        """Notebook chấm điểm gọi Solution(list_province=[...], list_ward=[...], list_street=[...]).
        Chạy ngoài notebook có thể truyền đường dẫn file (*_path); không truyền gì thì đọc data/."""
        self.list_province = list_province
        self.list_ward = list_ward
        self.list_street = list_street
        try:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        except NameError:   # trong notebook không có __file__
            data_dir = os.path.join(os.getcwd(), "data")
        sources = []
        for names, path, fname in ((list_street, street_path, "list_street.txt"),
                                   (list_ward, ward_path, "list_ward.txt"),
                                   (list_province, province_path, "list_province.txt")):
            if names is None:
                with open(path or os.path.join(data_dir, fname), encoding="utf-8-sig") as f:
                    names = f.read().splitlines()
            sources.append(names)
        self.list_street, self.list_ward, self.list_province = sources

        self.names = []                 # id -> tên gốc trong DB (giá trị trả về)
        self.groups = []                # id -> nhóm tiền tố của tên trong DB ("phuong", "xa"...) hoặc None
        self.accents = []               # id -> phần tên chính: có dấu, viết thường, không khoảng trắng
        self.tries = (Solution.Trie(), Solution.Trie(), Solution.Trie())
        self.initials = (Solution.Trie(), Solution.Trie(), Solution.Trie())  # chữ cái đầu của tên DB: "nkkn", "cmt8", "hcm"
        self.acronyms = ({}, {}, {})    # tên viết tắt trong DB ("LTK") -> so với chữ cái đầu của input
        self.holes = {}                 # "thi|minh|khai" + vị trí lỗ -> [(loại, id, độ dài từ gốc, từ gốc)]
        self.loose_by_first = {}        # từ đầu của tên -> [(loại, id, khoá, bigram của khoá)]
        self._first_cache = {}          # từ đầu của input -> [(từ đầu trong DB, số lỗi)]
        self.core_words = []            # id -> các từ (không dấu) của phần tên chính
        self.db_words = set()           # mọi từ (không dấu) xuất hiện trong tên DB
        self._ids = {}

        self.prefix_rows = Solution._prefix_rows()
        self.prefixes = Solution.Trie()   # khoá không dấu, giá trị (loại, nhóm, dạng có dấu)
        for etype, group, plain, acc in self.prefix_rows:
            self.prefixes.insert("".join(plain), (etype, group, "".join(acc)))
        self.prefix_words = {w for _, _, plain, _ in self.prefix_rows for w in plain}

        for etype, names in zip((Solution.STREET, Solution.WARD, Solution.PROVINCE), sources):
            for line in names:
                name = line.strip().lstrip("﻿").strip()
                if name and not name.startswith("#"):
                    self._add(etype, name)
        self.fuzzy_prefixes = self._build_fuzzy_prefixes()
        # chỉ mục xoá ký tự của các từ đầu (SymSpell): tra từ đầu sai < 60% bằng vài phép tra dict
        self.first_index = {}
        for v in self.loose_by_first:
            for d in Solution._deletes(v, Solution._first_word_budget(len(v))):
                self.first_index.setdefault(d, []).append(v)

    def _build_fuzzy_prefixes(self):
        """Mọi cách viết sai 1 lỗi (thêm / xoá / sửa / đảo, không đụng ký tự đầu) của các tiền tố dài.
        Bỏ cách viết trùng một từ có trong DB ("phung" ~ "phuong" nhưng Phùng là họ) hoặc trùng tiền tố khác."""
        letters = "abcdefghijklmnopqrstuvwxyz"
        exact = {"".join(plain) for _, _, plain, _ in self.prefix_rows}
        trie = Solution.Trie()
        for etype, group, plain, acc in self.prefix_rows:
            word = "".join(plain)
            if etype == Solution.ANY or len(word) < Solution.FUZZY_PREFIX_MIN_LEN:
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
        S, A, O, _, toks = Solution.analyze(name)
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
        self.core_words.append(tuple(core_words))
        self.db_words.update(words)
        trie = self.tries[etype]
        if Solution.HOLE_MIN_WORDS <= len(core_words) <= Solution.HOLE_MAX_WORDS:
            for h, w in enumerate(core_words):
                if w.isalpha():
                    self.holes.setdefault(Solution._hole_key(core_words, h), []).append((etype, eid, len(w), w))
        if core_words[0].isalpha() and key.isalpha() and len(key) >= Solution.LOOSE_MIN_LEN:
            self.loose_by_first.setdefault(core_words[0], []).append((etype, eid, key, Solution._bigrams(key)))

        if etype != Solution.STREET and (len(key) <= 2 or not any(c.isalpha() for c in key)):
            # "Phường 1", "Phường 12": tên quá ngắn / toàn số -> bắt buộc đi kèm tiền tố ("p1", "f12"...)
            for pt, g, plain, _ in self.prefix_rows:
                if pt == etype and (group is None or g == group):
                    trie.insert("".join(plain) + key, eid)
            return

        trie.insert(key, eid)
        if len(core_words) >= 3 or (etype == Solution.PROVINCE and group == "thanhpho" and len(core_words) == 2):
            self.initials[etype].insert(Solution._initials(core_words), eid)   # "hcm", "hn", "nkkn", "cmt8"
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
                    Solution._same_word(words[x], accs[x], plain[x], acc[x]) for x in range(m)):
                best_group, best_len = group, m
        return best_group, best_len

    # ------------------------------------------------------------------ xử lý 1 request
    def process(self, s):
        t_start = time.perf_counter()
        result = {f: Solution.NOT_FOUND for f in Solution.FIELDS}
        S, A, O, bound, tokens = Solution.analyze(s or "")
        n = len(S)
        if n == 0:
            return result
        ctx = (S, A, O, bound)

        # Lượt 1: chỉ khớp chính xác (rất nhanh)
        units = []
        for i in range(n):
            self._collect(ctx, i, n, (Solution.STREET, Solution.WARD, Solution.PROVINCE), False, units)
        self._collect_acronyms(S, tokens, units)
        chosen = Solution._best_segmentation(n, units)

        # Lượt 2: còn chữ cái nào chưa được giải thích thì tìm gần đúng (Levenshtein trên Trie)
        # từ mọi đầu từ. Chạy cả khi lượt 1 đã đủ 3 trường, vì lượt 1 có thể chỉ khớp được một tên
        # ngắn hơn ("Nam Kỳ" thay vì "Nam Ky Khoi Ngia") hoặc khớp nhầm.
        # Duyệt từ cuối chuỗi (tỉnh/phường thường nằm cuối) và dừng khi hết FUZZY_TIME_BUDGET:
        # chỉ input rất dài (kèm ghi chú hàng trăm ký tự) mới chạm giới hạn này.
        covered = bytearray(n)
        for u in chosen.values():
            covered[u[0]:u[1]] = b"\x01" * (u[1] - u[0])
        if any(S[p].isalpha() and not covered[p] for p in range(n)):
            deadline = min(time.perf_counter() + Solution.FUZZY_TIME_BUDGET, t_start + Solution.REQUEST_TIME_BUDGET)
            n_exact = len(units)
            self._collect_holes(ctx, tokens, covered, deadline, units)
            for s_i, (a, b) in enumerate(tokens):   # từ viết tắt đầu tên ("Ng T Minh Khai")
                if s_i + 1 < len(tokens) and S[a:b] in Solution.ABBREVIATIONS:
                    self._collect_abbrev(ctx, tokens, s_i, units)
            for i in range(n - 1, -1, -1):
                if bound[i]:
                    self._collect(ctx, i, n, (Solution.STREET, Solution.WARD, Solution.PROVINCE), True, units)
                    if time.perf_counter() > deadline:
                        break
            units = Solution._promote_containing(units, n_exact, n, bound)
            chosen = Solution._best_segmentation(n, units)

            # Lượt 3: vẫn còn chữ chưa giải thích -> khớp lỏng (sai / thiếu tới 40%, từ đầu sai < 60%)
            # "đã giải thích" = phần được chọn + mọi đoạn khớp CHÍNH XÁC một tên DB (kể cả không được chọn,
            # vd "Ba Đình" khi phường đã là Ngọc Hà): tên có thật thì không phải lỗi chính tả
            covered = bytearray(n)
            for u in list(chosen.values()) + units[:n_exact]:
                covered[u[0]:u[1]] = b"\x01" * (u[1] - u[0])
            if len(chosen) < 3 and time.perf_counter() < deadline and \
                    any(S[p].isalpha() and not covered[p] for p in range(n)):
                types = tuple(t for t in (Solution.STREET, Solution.WARD, Solution.PROVINCE) if t not in chosen)
                self._collect_loose(ctx, tokens, covered, types, deadline, units)
                chosen = Solution._best_segmentation(n, units)

        for t, u in chosen.items():
            result[Solution.FIELDS[t]] = self.names[u[4]]
        return result

    def _collect(self, ctx, i, end, types, fuzzy, out):
        """Sinh ứng viên bắt đầu tại i; tên có thể đi sau một tiền tố hành chính ("P.", "Tỉnh"...)."""
        S, A, O, bound = ctx
        starts = [(i, None, Solution.PREFIX_BONUS)]
        keyword = False  # từ tại i là nguyên một tiền tố ("phuong", "tp", "quan"...)
        for k, infos, _ in self.prefixes.exact(S, i, end):
            acc = A[i:k]
            if acc != S[i:k]:  # input có dấu: cho sai 1 dấu ("Phuờng"), nhưng "Dương" (2 dấu) ≠ "Đường"
                infos = [x for x in infos if sum(a != b for a, b in zip(acc, x[2])) <= 1]
            if k < end and infos:
                starts.append((k, infos, Solution.PREFIX_BONUS))
                keyword = keyword or bool(bound[k])
        if bound[i]:
            # tiền tố viết sai 1 lỗi: phải đứng thành từ riêng, và dấu của input (nếu có) phải là dấu
            # của tiền tố ("Phưường" được, "Phùng" không)
            for k, infos, _ in self.fuzzy_prefixes.exact(S, i, end):
                if k < end and bound[k]:
                    marks = [c for c in A[i:k] if c > "\x7f"]
                    infos = [x for x in infos if all(c in x[2] for c in marks)]
                    if infos:
                        starts.append((k, infos, -Solution.FUZZY_PREFIX_PENALTY))
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
                        if pt == Solution.ANY:
                            ok = True
                    if not ok:
                        continue
                trie = self.tries[t]
                if fuzzy:
                    matches = trie.fuzzy(S, k, end)
                    if Solution.HEAD_FIX:
                        for j, ids, edits, penalty in trie.fuzzy_head(S, k, end):
                            unit = self._score(ctx, i, k, j, t, ids, edits, group, bonus)
                            if unit is not None and unit[3] - penalty >= max(2.0, 0.5 * (j - i)):
                                out.append(unit[:3] + (unit[3] - penalty,) + unit[4:])
                else:
                    matches = trie.exact(S, k, end)
                    for m in self.initials[t].exact(S, k, end):
                        # viết tắt đường/phường phải viết HOA ("NKKN"), để "khu" không thành "Kiều Hòa Uyên"
                        if t == Solution.PROVINCE or O[k:m[0]].isupper():
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
        score = covered - Solution.EDIT_PENALTY * edits + bonus + Solution.TYPE_BIAS[t]
        if not bound[i]:
            score -= Solution.BOUNDARY_PENALTY
        if not bound[j]:
            score -= Solution.BOUNDARY_PENALTY
        if score < max(2.0, 0.5 * covered):
            return None
        if t == Solution.STREET and i > 0 and S[i - 1].isdigit():
            score += Solution.HOUSE_NUMBER_BONUS
        eid = self._pick(ids, group, A[k:j])
        if edits and j - k <= Solution.SHORT_NAME_LEN:
            # tên ngắn sửa lỗi: input có dấu thì tập dấu phải trùng tên DB
            # ("Bàn Lờ" -> Bàn Cờ được; "Lê Lai" -> Lê Lợi không, vì đó là một tên khác)
            marks = sorted(c for c in A[k:j] if c > "\x7f")
            if marks and marks != sorted(c for c in self.accents[eid] if c > "\x7f"):
                return None
        if group is not None and self.groups[eid] == group:
            score += Solution.GROUP_BONUS
        marks = [c for c in A[k:j] if c > "\x7f"]
        if marks:
            ref = self.accents[eid]
            score += Solution.ACCENT_BONUS * sum(c in ref for c in marks) / len(marks)
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
            for m in range(Solution.HOLE_MIN_WORDS, min(Solution.HOLE_MAX_WORDS, len(words) - a) + 1):
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
                    hits = [x for x in self.holes.get(Solution._hole_key(window, h), ())
                            if abs(x[2] - len(w)) <= Solution.HOLE_LEN_DIFF]
                    if len({x[1] for x in hits}) != 1:
                        continue
                    t, eid, _, orig = hits[0]
                    if h == 0 and Solution._lev(w, orig) > Solution._first_word_budget(len(orig)):
                        continue  # từ đầu sai >= 60%: bỏ, xét ứng viên khác
                    i, j = tokens[a][0], tokens[a + m - 1][1]
                    unit = self._score(ctx, i, i, j, t, [eid], 0, None, 0.0)
                    if unit is None:
                        continue
                    score = unit[3] - (we - ws) - Solution.HOLE_PENALTY
                    if score >= max(2.0, 0.5 * (j - i - (we - ws))):
                        out.append(unit[:3] + (score,) + unit[4:])

    def _first_matches(self, q):
        """Các từ đầu trong DB cách q < 60% số ký tự (theo độ dài từ DB). Có cache theo q."""
        hit = self._first_cache.get(q)
        if hit is None:
            cands = set()
            for d in Solution._deletes(q, min(4, Solution._first_word_budget(len(q) + 2))):
                cands.update(self.first_index.get(d, ()))
            hit = []
            for v in cands:
                e = Solution._lev(q, v)
                if e <= Solution._first_word_budget(len(v)):
                    hit.append((v, e))
            if len(self._first_cache) > 50000:
                self._first_cache.clear()
            self._first_cache[q] = hit
        return hit

    def _collect_loose(self, ctx, tokens, covered, types, deadline, out):
        """Khớp lỏng cho các loại còn thiếu, chỉ bắt đầu ở từ CHƯA được giải thích.

        1. Từ đầu tại vị trí đó phải khớp từ đầu của tên DB với sai < 60% (tra chỉ mục SymSpell).
        2. Các tên có từ đầu đó: lọc bằng số bigram chung (mỗi lỗi làm mất tối đa 2 bigram),
           xếp theo tỉ lệ bigram chung, lấy LOOSE_TOP tên.
        3. Levenshtein neo tại đầu từ, kết thúc ở ranh giới từ: tổng lỗi <= 40% độ dài tên.
        Thiếu từ ("Nam Kỳ Nghĩa") được tính là lỗi xoá ký tự nên cũng nằm trong 40%.
        """
        S, A, O, bound = ctx
        n = len(S)
        starts = []   # (token bắt đầu tên, vị trí bắt đầu ứng viên (kể cả tiền tố), loại cho phép, thưởng, nhóm)
        for s, (a, b) in enumerate(tokens):
            if covered[a]:
                continue
            keyword = False
            for k, infos, _ in self.prefixes.exact(S, a, n):
                if not bound[k] or k >= n:
                    continue
                acc = A[a:k]
                if acc != S[a:k]:  # input có dấu: "Dương" (họ) không phải tiền tố "Đường"
                    infos = [x for x in infos if sum(c != d for c, d in zip(acc, x[2])) <= 1]
                s2 = next((x for x in range(s + 1, len(tokens)) if tokens[x][0] == k), None)
                if not infos or s2 is None or covered[k]:
                    continue
                keyword = True
                for pt, g, _ in infos:
                    if pt == Solution.ANY:
                        starts.append((s2, a, types, 0.0, None))
                    elif pt in types:
                        starts.append((s2, a, (pt,), Solution.PREFIX_BONUS, g))
            if not keyword:
                starts.append((s, a, types, 0.0, None))

        seen = set()
        for s, i, allowed, bonus, group in starts:
            if time.perf_counter() > deadline:
                return
            k, kb = tokens[s]
            q = S[k:kb]
            if not q.isalpha():
                continue
            if q in Solution.ABBREVIATIONS:
                continue   # lượt 2 đã xử lý bằng _collect_abbrev
            window = Solution._bigrams(S[k:k + 48])
            pool = []
            for v, _ in self._first_matches(q):
                for t, eid, key, bg in self.loose_by_first[v]:
                    if t not in allowed or (i, t, eid) in seen:
                        continue
                    shared = len(bg & window)
                    if shared and shared >= len(bg) - 2 * Solution._loose_budget(len(key)):
                        pool.append((shared / len(bg), t, eid, key))
            pool.sort(reverse=True)
            for _, t, eid, key in pool[:Solution.LOOSE_TOP]:
                seen.add((i, t, eid))
                budget = Solution._loose_budget(len(key))
                m = Solution._anchored_lev(key, S, k, min(n, k + len(key) + budget), bound, budget)
                if m is None:
                    continue
                edits, j = m
                if any(c.isdigit() for c in S[k:j]):
                    continue
                if len(key) <= Solution.SHORT_NAME_LEN and edits:
                    marks = sorted(c for c in A[k:j] if c > "\x7f")
                    if marks and marks != sorted(c for c in self.accents[eid] if c > "\x7f"):
                        continue  # tên ngắn, input có dấu mà khác dấu: là tên khác ("Lê Lai" ≠ Lê Lợi)
                score = (j - i) - Solution.LOOSE_EDIT_PENALTY * edits - Solution.LOOSE_PENALTY + bonus + Solution.TYPE_BIAS[t]
                if not bound[i]:
                    score -= Solution.BOUNDARY_PENALTY
                if t == Solution.STREET and i > 0 and S[i - 1].isdigit():
                    score += Solution.HOUSE_NUMBER_BONUS
                if group is not None and self.groups[eid] == group:
                    score += Solution.GROUP_BONUS
                if score >= Solution.LOOSE_MIN_SCORE:
                    out.append((i, j, t, score, eid))

    def _collect_abbrev(self, ctx, tokens, s, out):
        """Tên bắt đầu bằng từ viết tắt ("Ng T Minh Khai", "Tr. Hưng Đạo"), so khớp THEO TỪ.

        Từ đầu tra bảng ABBREVIATIONS (mọi giá trị đều được thử). Các từ sau: khớp đúng (0), viết tắt
        1 chữ cái ("T" -> Thị) hoặc từ trong bảng (ABBREV_COST), sai chính tả (Levenshtein, < 60% từ),
        thiếu từ (độ dài từ) hoặc dư 1 token nhiễu ở giữa (độ dài token). Tổng lỗi (không tính viết tắt)
        <= 40% độ dài tên; TỪ CUỐI (tên chính) phải khớp, không được viết tắt.
        """
        S, A, _, bound = ctx
        n = len(S)
        words = [S[a:b] for a, b in tokens]
        q = words[s]
        i = tokens[s][0]
        INF = float("inf")
        best = {}   # (t, eid) -> (score, j)
        # lọc nhanh: từ cuối, hoặc >= 2 từ sau từ đầu, phải khớp đúng 1 token / 2 token liền nhau ("Kh*ai")
        win = set()
        for x in range(s + 1, min(len(words), s + 9)):
            win.add(words[x])
            if x + 1 < len(words):
                win.add(words[x] + words[x + 1])
        near = {}   # cache: từ cuối của tên -> có token nào trong cửa sổ sai < 60% không
        for rank, v in enumerate(Solution.ABBREVIATIONS[q]):
            for t, eid, key, _ in self.loose_by_first.get(v, ()):
                name = self.core_words[eid]
                m = len(name)
                if m < 2:
                    continue
                hit = sum(w in win for w in name[1:])
                if not (name[-1] in win or hit >= 2 or (hit and self._near_any(name[-1], win, near))):
                    continue
                budget = Solution._loose_budget(len(key))
                hi = min(len(words), s + m + 2)
                # dp[a][b]: (lỗi, số viết tắt) tốt nhất khi đã khớp a từ của tên với token s..s+b-1
                W = hi - s
                dp = [[None] * (W + 1) for _ in range(m + 1)]
                dp[1][1] = (0, 1)            # từ đầu = viết tắt q của v
                last_match = [[False] * (W + 1) for _ in range(m + 1)]
                for a in range(1, m + 1):
                    for b in range(1, W + 1):
                        cur = dp[a][b]
                        if cur is None:
                            continue
                        e, ab = cur
                        if e > budget:
                            continue
                        cands = []
                        if a < m:
                            w = name[a]
                            cands.append((a + 1, b, e + len(w), ab, False))          # thiếu từ w
                            if b < W:
                                tok = words[s + b]
                                if tok == w:
                                    cands.append((a + 1, b + 1, e, ab, True))
                                elif tok.isalpha() and (
                                        (len(tok) == 1 and w[0] == tok) or
                                        w in Solution.ABBREVIATIONS.get(tok, ())):
                                    if a + 1 < m:                                 # từ cuối không viết tắt
                                        cands.append((a + 1, b + 1, e, ab + 1, False))
                                elif tok.isalpha():
                                    d = Solution._lev(tok, w)
                                    if d <= Solution._first_word_budget(len(w)):
                                        cands.append((a + 1, b + 1, e + d, ab, True))
                                if b + 1 < W and words[s + b + 1].isalpha():   # từ bị nhiễu tách đôi
                                    two = tok + words[s + b + 1]
                                    d = 0 if two == w else Solution._lev(two, w)
                                    if d <= Solution._first_word_budget(len(w)) // 2:
                                        cands.append((a + 1, b + 2, e + d, ab, True))
                        if b < W and 0 < a < m and words[s + b].isalpha() and len(words[s + b]) <= 2:
                            cands.append((a, b + 1, e + len(words[s + b]), ab, False))  # token nhiễu ngắn
                        for na, nb, ne, nab, matched in cands:
                            old = dp[na][nb]
                            if ne <= budget and (old is None or (ne, nab) < old):
                                dp[na][nb] = (ne, nab)
                                last_match[na][nb] = matched
                for b in range(2, W + 1):
                    cur = dp[m][b]
                    if cur is None or not last_match[m][b]:
                        continue
                    e, ab = cur
                    j = tokens[s + b - 1][1]
                    score = (j - i) - Solution.LOOSE_EDIT_PENALTY * e - Solution.ABBREV_COST * ab \
                        - Solution.LOOSE_PENALTY + Solution.TYPE_BIAS[t] - Solution.ABBREV_ORDER_PENALTY * rank
                    if t == Solution.STREET and i > 0 and S[i - 1].isdigit():
                        score += Solution.HOUSE_NUMBER_BONUS
                    k0 = tokens[s + 1][0]
                    marks = [c for c in A[k0:j] if c > "\x7f"]
                    if marks:   # dấu của phần còn lại phá thế hoà ("Ng Huệ": Nguyễn Huệ / Ngô Huệ)
                        ref = self.accents[eid]
                        score += Solution.ACCENT_BONUS * sum(c in ref for c in marks) / len(marks)
                    if score >= Solution.LOOSE_MIN_SCORE and score > best.get((t, eid), (-INF,))[0]:
                        best[(t, eid)] = (score, j)
        for (t, eid), (score, j) in best.items():
            out.append((i, j, t, score, eid))

    @staticmethod
    def _near_any(w, win, cache):
        r = cache.get(w)
        if r is None:
            k = Solution._first_word_budget(len(w))
            r = cache[w] = any(abs(len(x) - len(w)) <= k and Solution._lev(x, w) <= k for x in win)
        return r

    def _collect_acronyms(self, S, tokens, out):
        """Input viết đầy đủ ("Lý Thường Kiệt") nhưng DB lưu viết tắt ("LTK")."""
        if not any(self.acronyms):
            return
        words = [S[a:b] for a, b in tokens]
        for a in range(len(words)):
            for b in range(a + 2, min(len(words), a + 8) + 1):
                key = Solution._initials(words[a:b])
                for t in (Solution.STREET, Solution.WARD, Solution.PROVINCE):
                    ids = self.acronyms[t].get(key)
                    if ids:
                        i, j = tokens[a][0], tokens[b - 1][1]
                        out.append((i, j, t, (j - i) - Solution.ACRONYM_PENALTY + Solution.TYPE_BIAS[t], ids[0]))

# %% cell 6
# Download public test
# !rm -rf test.json
# !gdown --fuzzy https://drive.google.com/file/d/18qzaHmx9-fcKPi4gTq304G2JvXy_g6XW/view?usp=sharing -O test.json
# !gdown --fuzzy https://drive.google.com/file/d/1PHRkRLRaO2vFivLbcPJsaxjvZ7K_I3lU/view?usp=drive_link -O list_province.txt
# !gdown --fuzzy https://drive.google.com/file/d/1QrSouYn6IUEW7Impje1vOxzsksjlAJ-h/view?usp=drive_link -O list_ward.txt
# !gdown --fuzzy https://drive.google.com/file/d/1yP2dBE8K9QtUiaLPewtQRr-hDH0gOgfa/view?usp=drive_link -O list_street.txt

# %% cell 7
def _judge_normalize(s: str, context=None):
    return s

EXCEL_FILE = f'{TEAM_NAME}.xlsx'

import json
import time
with open('test.json') as f:
    data = json.load(f)

with open("list_province.txt") as f:
    list_province = f.read().strip().splitlines()

with open("list_ward.txt") as f:
    list_ward = f.read().strip().splitlines()

with open("list_street.txt") as f:
    list_street = f.read().strip().splitlines()

summary_only = True
df = []
solution = Solution(
    list_province=list_province,
    list_ward=list_ward,
    list_street=list_street,
)
timer = []
correct = 0
for test_idx, data_point in enumerate(data):
    address = data_point["address"]

    ok = 0
    try:
        answer = data_point["result"]
        answer["province_normalized"] = _judge_normalize(answer["province"])
        answer["ward_normalized"] = _judge_normalize(answer["ward"])
        answer["street_normalized"] = _judge_normalize(answer["street"])

        start = time.perf_counter_ns()
        result = solution.process(address)
        finish = time.perf_counter_ns()
        timer.append(finish - start)
        result["province_normalized"] = _judge_normalize(result["province"])
        result["ward_normalized"] = _judge_normalize(result["ward"])
        result["street_normalized"] = _judge_normalize(result["street"])

        province_correct = int(answer["province_normalized"] == result["province_normalized"])
        ward_correct = int(answer["ward_normalized"] == result["ward_normalized"])
        street_correct = int(answer["street_normalized"] == result["street_normalized"])
        ok = province_correct + street_correct + ward_correct

        df.append([
            test_idx,
            address,

            answer["province"],
            result["province"],
            answer["province_normalized"],
            result["province_normalized"],
            province_correct,

            answer["ward"],
            result["ward"],
            answer["ward_normalized"],
            result["ward_normalized"],
            ward_correct,

            answer["street"],
            result["street"],
            answer["street_normalized"],
            result["street_normalized"],
            street_correct,

            ok,
            timer[-1] / 1_000_000_000,
        ])
    except Exception as e:
        print(f"{answer = }")
        print(f"{result = }")
        df.append([
            test_idx,
            address,

            answer["province"],
            "EXCEPTION",
            answer["province_normalized"],
            "EXCEPTION",
            0,

            answer["ward"],
            "EXCEPTION",
            answer["ward_normalized"],
            "EXCEPTION",
            0,

            answer["street"],
            "EXCEPTION",
            answer["street_normalized"],
            "EXCEPTION",
            0,

            0,
            0,
        ])
        # any failure count as a zero correct
        pass
    correct += ok


    if not summary_only:
        # responsive stuff
        print(f"Test {test_idx:5d}/{len(data):5d}")
        print(f"Correct: {ok}/3")
        print(f"Time Executed: {timer[-1] / 1_000_000_000:.4f}")


print(f"-"*30)
total = len(data) * 3
score_scale_10 = round(correct / total * 10, 2)
if len(timer) == 0:
    timer = [0]
max_time_sec = round(max(timer) / 1_000_000_000, 4)
avg_time_sec = round((sum(timer) / len(timer)) / 1_000_000_000, 4)

import pandas as pd

df2 = pd.DataFrame(
    [[correct, total, score_scale_10, max_time_sec, avg_time_sec]],
    columns=['correct', 'total', 'score / 10', 'max_time_sec', 'avg_time_sec',],
)

columns = [
    'ID',
    'text',

    'province',
    'province_student',
    'province_normalized',
    'province_student_normalized',
    'province_correct',

    'ward',
    'ward_student',
    'ward_normalized',
    'ward_student_normalized',
    'ward_correct',

    'street',
    'street_student',
    'street_normalized',
    'street_student_normalized',
    'street_correct',

    'total_correct',
    'time_sec',
]

df = pd.DataFrame(df)
df.columns = columns

print(f'{TEAM_NAME = }')
print(f'{EXCEL_FILE = }')
print(df2)

# !pip install xlsxwriter
writer = pd.ExcelWriter(EXCEL_FILE, engine='xlsxwriter')
df2.to_excel(writer, index=False, sheet_name='summary')
df.to_excel(writer, index=False, sheet_name='details')
writer.close()

