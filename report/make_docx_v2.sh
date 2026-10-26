#!/bin/bash
# レポートの編集用 Word（.docx）を作る（LibreOffice を使う。コンテナ内で実行）。
#   docker exec -u ubuntu -w /workspace pai_ros2 bash report/make_docx.sh
# 手順：report_v2.html → 画像を埋め込んだ HTML → .docx。構成図は PNG（report/diagram.png）を使う。
set -e
cd /workspace/report
mkdir -p docx_build; cp diagram.png docx_build/
python3 - <<'PY'
import re, base64, os
html = open('report_v2.html').read()
html = re.sub(r'<figure>\s*<svg.*?</svg>', '<figure><img src="diagram.png" width="640">', html, flags=re.S)
html = html.replace('<table>', '<table border="1" cellpadding="4" cellspacing="0" width="100%">')
def fix_img(m):
    tag = m.group(0)
    half = 'width:49%' in tag
    tag = re.sub(r'\sstyle="[^"]*"', '', tag)
    return tag if 'width=' in tag else tag.replace('<img', '<img width="%d"' % (310 if half else 600))
html = re.sub(r'<img[^>]*>', fix_img, html)
html = html.replace('<figure>', '<div>').replace('</figure>', '</div>').replace('<figcaption>', '<p><i>').replace('</figcaption>', '</i></p>')
def emb(m):
    full = os.path.normpath(os.path.join('docx_build' if m.group(1) == 'diagram.png' else '.', m.group(1)))
    return 'src="data:image/png;base64,%s"' % base64.b64encode(open(full, 'rb').read()).decode()
open('docx_build/report_v2_emb.html', 'w').write(re.sub(r'src="([^"]+\.png)"', emb, html))
PY
cd docx_build
HOME=/tmp soffice --headless --infilter="HTML (StarWriter)" --convert-to docx:"MS Word 2007 XML" report_v2_emb.html
echo "できました: report/docx_build/report_v2_emb.docx"
