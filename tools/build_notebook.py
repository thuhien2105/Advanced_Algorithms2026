# -*- coding: utf-8 -*-
"""Tạo notebook nộp bài từ template của thầy (notebook/GettingStarted_v2.ipynb) + solution.py.

Theo hướng dẫn nộp bài:
  cell 1  TEAM_NAME = 'Group_xx'
  cell 2  tải DB riêng bằng gdown        -> không dùng (chỉ dùng 3 list thầy đưa vào Solution)
  cell 3  MỌI lệnh pip install           -> không cần (chỉ dùng thư viện chuẩn)
  cell 4  import thư viện
  cell 5  class Solution                 -> lấy nguyên từ solution.py (mọi hằng số / hàm nằm TRONG class)
  2 cell cuối: tải public test + chấm điểm -> giữ NGUYÊN của thầy (bị thay khi chấm)

    python tools/build_notebook.py --team Group_07
Kết quả: notebook/<team>.ipynb và notebook/<team>.py (cùng nội dung code, để nộp kèm).
"""
import argparse
import copy
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "notebook", "GettingStarted_v2.ipynb")
END_MARK = "# ==== HẾT PHẦN NỘP"


def solution_parts():
    """(các dòng import, mã class Solution) từ solution.py."""
    with open(os.path.join(ROOT, "solution.py"), encoding="utf-8") as f:
        src = f.read()
    start = src.index("class Solution:")
    end = src.index(END_MARK)
    imports = re.findall(r"^(?:import|from) .+$", src[:start], re.M)
    return imports, src[start:end].rstrip() + "\n"


def lines(text):
    out = text.splitlines(keepends=True)
    if out:
        out[-1] = out[-1].rstrip("\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="Group_xx")
    args = ap.parse_args()

    with open(TEMPLATE, encoding="utf-8") as f:
        nb = json.load(f)
    imports, cls = solution_parts()
    cells = nb["cells"]
    assert len(cells) == 7 and "class Solution" in "".join(cells[4]["source"]), "template đổi cấu trúc?"

    new = {
        0: "# Change your team name to Group_xx\nTEAM_NAME = '%s'" % args.team,
        1: "# NOTE: you CAN change this cell\n# If you want to use your own database, download it here\n"
           "# Không dùng DB riêng: chỉ dùng list_province / list_ward / list_street truyền vào Solution",
        2: "# NOTE: you CAN change this cell\n# Add more to your needs\n# you must place ALL pip install here\n"
           "# Không cần cài thêm: lời giải chỉ dùng thư viện chuẩn của Python",
        3: "# NOTE: you CAN change this cell\n# import your library here\n" + "\n".join(imports),
        4: "# NOTE: you MUST change this cell\n# New methods / functions must be written under class Solution.\n" + cls,
    }
    out = copy.deepcopy(nb)
    for i, c in enumerate(out["cells"]):
        if i in new:
            c["source"] = lines(new[i])
        c["outputs"], c["execution_count"] = [], None

    os.makedirs(os.path.join(ROOT, "notebook"), exist_ok=True)
    ipynb = os.path.join(ROOT, "notebook", args.team + ".ipynb")
    with open(ipynb, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    # bản .py để nộp kèm: các cell nối lại, lệnh shell (!...) để dạng comment
    py = os.path.join(ROOT, "notebook", args.team + ".py")
    with open(py, "w", encoding="utf-8") as f:
        for i, c in enumerate(out["cells"]):
            code = "".join(c["source"])
            code = re.sub(r"^(\s*)!", r"\1# !", code, flags=re.M)
            f.write("# %%%% cell %d\n%s\n\n" % (i + 1, code))
    print("đã ghi", ipynb, "và", py)


if __name__ == "__main__":
    main()
