#!/usr/bin/env python3
"""v2（44 t 級の車両）のレポートの HTML を生成する（結果の表は results/*.csv から作る）。

使い方:  python3 report/build_report_v2.py > report/report_v2.html
PDF は Chrome の headless で作る:
  chrome --headless=new --no-pdf-header-footer --print-to-pdf=report_v2.pdf file:///.../report/report_v2.html
"""
import csv
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    with open(os.path.join(ROOT, "results", name + ".csv")) as f:
        return list(csv.DictReader(f))


def m(rows, key):
    v = [float(r[key]) for r in rows]
    return st.mean(v) if v else float("nan")


def berm_table():
    spec = [("一定スロットル 1.0（全開）", "v2_berm_const_1.0", "bad"), ("一定スロットル 0.5", "v2_berm_const_0.5", ""),
            ("一定スロットル 0.25", "v2_berm_const_0.25", ""), ("一定スロットル 0.15", "v2_berm_const_0.15", ""),
            ("<b>ACT（観測 8 次元：throttle_cmd あり）</b>", "v2_berm_policy_cmd_n8", "best"),
            ("<b>ACT（観測 7 次元：throttle_cmd なし）</b>", "v2_berm_policy_nocmd_n8", "best")]
    out = ['<table><tr><th class="l">方式</th><th>通過</th><th>跳ねずに通過</th><th>着地衝撃（平均／最大）</th><th>所要時間</th></tr>']
    for label, f, cls in spec:
        d = load(f)
        p = sum(r["reached"] == "True" for r in d)
        h = sum(r["no_hop_pass"] == "True" for r in d)
        imp = [float(r["impact"]) for r in d]
        out.append(f'<tr class="{cls}"><td class="l">{label}</td><td>{p}/{len(d)}</td><td>{h}/{len(d)}</td>'
                   f'<td>{st.mean(imp):.2f}／{max(imp):.2f} m/s</td><td>{m(d, "time_sec"):.1f} s</td></tr>')
    out.append('<tr class="human"><td class="l">人のデモ 10 本（記録の概算）</td><td>10/10</td><td>―</td><td>1.2〜2.7 m/s（10 Hz の概算）</td><td>14.9 s</td></tr>')
    out.append("</table>")
    return "\n".join(out)


def ditch_table():
    spec = [("人のデモ 10 本の再生", "v2_ditch_human_replay2", "human"),
            ("一定スロットル 0.15", "v2_ditch_const015", ""),
            ("全開のまま", "v2_ditch_full", "bad"),
            ("ルール：x=70 m から 0.15、x=112 m から全開", "v2_ditch_slowzone", ""),
            ("<b>ACT（観測：数値のみ）</b>", "v2_ditch_policy_t90nocmd_n8_new", "best"),
            ("ACT（観測：数値＋画像）1 回目", "v2_ditch_policy_t90imgnocmd_n8_new", ""),
            ("ACT（観測：数値＋画像）2 回目", "v2_ditch_policy_t90imgnocmd_n8_new2", "")]
    out = ['<table><tr><th class="l">方式</th><th>通過</th><th>飛ばずに通過</th><th>着地衝撃 入る／出る</th><th>所要時間</th></tr>']
    for label, f, cls in spec:
        d = load(f)
        ok = [r for r in d if r["outcome"] == "passed"]
        nh = sum(1 for r in ok if float(r["impact_in"]) < 3.0 and float(r["impact_out"]) < 3.0)   # 入るときも出るときも 3.0 m/s 未満
        cells = (f'{m(ok, "impact_in"):.2f}／{m(ok, "impact_out"):.2f} m/s', f'{m(ok, "time_sec"):.1f} s') if ok else ("―", "―")
        out.append(f'<tr class="{cls}"><td class="l">{label}</td><td>{len(ok)}/{len(d)}</td><td>{nh}/{len(d)}</td>'
                   + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def diagram():
    with open(os.path.join(ROOT, "report", "diagram.svg")) as f:
        return f.read()


HTML = open(os.path.join(ROOT, "report", "report_v2_template.html"), encoding="utf-8").read()


def main():
    html = HTML.replace("__DIAGRAM__", diagram()).replace("__BERM_TABLE__", berm_table()).replace("__DITCH_TABLE__", ditch_table())
    print(html)


if __name__ == "__main__":
    main()
