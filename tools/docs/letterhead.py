"""Shared letterhead, statutory footer and PDF rendering for the Turkish entity.

TTK art. 39: business documents carry the trade name, registered office,
trade registry and number, and MERSIS number. The full legal name sits in the
header of every document; the statutory line repeats it in the footer.
"""
import html
import json
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
e = html.escape


def load_firm(path=None):
    with open(path or os.path.join(HERE, "firm_tr.json"), encoding="utf-8") as f:
        return json.load(f)


CSS = """
@page{size:A4}
body{font-family:Georgia,'Times New Roman',serif;color:#111;margin:0}
.lh{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;
    border-bottom:1.5px solid #111;padding-bottom:9px;margin-bottom:14px}
.lh .wm{font-size:19pt;letter-spacing:6px;font-weight:bold;line-height:1}
.lh .ln{font-size:7.9pt;letter-spacing:.6px;text-transform:uppercase;margin-top:5px;max-width:360px;line-height:1.35}
.lh .ad{font-size:8pt;color:#444;text-align:right;line-height:1.45;white-space:nowrap}
.stat{font-size:7.6pt;color:#555;border-top:1px solid #bbb;padding-top:6px;margin-top:14px;line-height:1.4}
"""


def header(f):
    contact = [e(x) for x in f["address_lines"]]
    for k in ("phone", "email", "web"):
        if f.get(k):
            contact.append(e(f[k]))
    return (f'<div class="lh"><div><div class="wm">{e(f["wordmark"])}</div>'
            f'<div class="ln">{e(f["legal_name"])}</div></div>'
            f'<div class="ad">{"<br>".join(contact)}</div></div>')


def statutory(f):
    return (f'<div class="stat">{e(f["legal_name"])} · {e(f["trade_registry"])} · '
            f'MERSİS No: {e(f["mersis"])} · {e(f["tax_office"])} Vergi Dairesi: {e(f["tax_no"])} · '
            f'{e(f["address_one_line"])}' + (f' · {e(f["web"])}' if f.get("web") else "") + '</div>')


def footer_template(f, ref):
    return ('<div style="width:100%;font-family:Georgia,serif;font-size:7.3pt;color:#555;text-align:center">'
            f'{e(f["short_name"])} · {e(ref)} · Strictly private and confidential · '
            'Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>')


RENDER_JS = r"""
const {chromium}=require('playwright');(async()=>{
const [,,src,out,foot,top,bottom]=process.argv;
const b=await chromium.launch();const p=await b.newPage();
await p.goto('file://'+src);
await p.pdf({path:out,format:'A4',displayHeaderFooter:true,headerTemplate:'<span></span>',
 footerTemplate:foot,margin:{top:top,bottom:bottom,left:'20mm',right:'20mm'}});
await b.close();})();
"""


def render_pdf(html_path, pdf_path, f, ref, top="16mm", bottom="18mm"):
    js = os.path.join(tempfile.gettempdir(), "chapra_render.js")
    with open(js, "w") as fh:
        fh.write(RENDER_JS)
    subprocess.run(["node", js, os.path.abspath(html_path), os.path.abspath(pdf_path),
                    footer_template(f, ref), top, bottom], check=True)
    out = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout
    pages = int([l for l in out.splitlines() if l.startswith("Pages:")][0].split()[1])
    return pages
