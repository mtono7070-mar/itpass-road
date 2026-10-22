"""index.html（予約ページ）と admin.html（管理画面）を1ページにまとめた demo.html を作る。

claude.ai の公開ページはページごとに1つのデータベースを持つので、2つの画面を
同じページに入れて上部のボタンで切り替える。index.html / admin.html を直したら
`python3 salon/build_demo.py` で作り直す。
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
cust = (HERE / "index.html").read_text(encoding="utf-8")
admin = (HERE / "admin.html").read_text(encoding="utf-8")
store = (HERE / "store.js").read_text(encoding="utf-8")


def between(s, start, end):
    i = s.index(start) + len(start)
    return s[i:s.index(end, i)]


def rules(css):
    """トップレベルの (セレクタ, 中身) を順に返す。"""
    out, i = [], 0
    while True:
        j = css.find("{", i)
        if j < 0:
            return out
        depth, k = 1, j + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        out.append((css[i:j].strip(), css[j + 1:k - 1]))
        i = k


SHARED_BASE = {"*", "html", "body", "[hidden]", "h1,h2,h3", "button,input,select,textarea", "button", ".toast"}


def scope(css, prefix):
    """管理画面の CSS を prefix の中だけに効くようにする（テーマ色の定義はそのまま）。"""
    out = []
    for sel, body in rules(css):
        if sel.startswith(":root") or "prefers-color-scheme" in sel:
            out.append(f"{sel}{{{body}}}")
        elif sel.startswith("@media"):
            out.append(f"{sel}{{\n{scope(body, prefix)}\n}}")
        elif sel in SHARED_BASE:
            continue
        else:
            parts = [f"{prefix} {p.strip()}" for p in sel.split(",")]
            out.append(f"{','.join(parts)}{{{body}}}")
    return "\n".join(out)


cust_css = between(cust, "<style>\n", "</style>")
admin_css = scope(between(admin, "<style>\n", "</style>"), "#adminView")

cust_body = between(cust, "<body>\n", '<script src="store.js"></script>')
admin_body = between(admin, "<body>\n", '<script src="store.js"></script>')
cust_body = re.sub(r'<div class="toast" id="toast" hidden></div>\s*', "", cust_body)
admin_body = re.sub(r'<div class="toast" id="toast" hidden></div>\s*', "", admin_body)
admin_body = admin_body.replace(
    '<a class="btn plain" href="./" style="text-decoration:none">予約ページ</a>',
    '<button class="btn plain" type="button" data-view="cust">予約ページ</button>')
assert 'data-view="cust"' in admin_body

cust_js = between(cust, '<script src="store.js"></script>\n<script>\n', "</script>")
admin_js = between(admin, '<script src="store.js"></script>\n<script>\n', "</script>")

head = cust[:cust.index("<style>\n")]
head = head.replace("<title>yosayosapark yuki ご予約</title>", "<title>yosayosapark yuki 予約デモ</title>")

page = f"""{head}<style>
{cust_css}
/* ---- 管理画面 ---- */
{admin_css}
/* ---- デモの切り替え ---- */
.switcher{{position:sticky;top:0;z-index:50;display:flex;gap:6px;align-items:center;justify-content:center;flex-wrap:wrap;padding:8px 16px;background:var(--ink);color:var(--bg);font-size:12px}}
.switcher span{{opacity:.75;margin-right:4px}}
.switcher button{{border:1px solid color-mix(in srgb,var(--bg) 40%,transparent);background:transparent;color:var(--bg);border-radius:999px;padding:4px 14px;font-size:13px}}
.switcher button[aria-pressed="true"]{{background:var(--bg);color:var(--ink);border-color:var(--bg);font-weight:700}}
#custView header.top,#adminView header.top{{position:sticky;top:var(--swh,44px)}}
#custView section.block{{scroll-margin-top:calc(56px + var(--swh,44px))}}
</style>
</head>
<body>

<nav class="switcher" aria-label="画面の切り替え">
  <span>デモ</span>
  <button type="button" data-view="cust" aria-pressed="true">お客様の予約画面</button>
  <button type="button" data-view="admin" aria-pressed="false">お店の管理画面</button>
</nav>

<div id="custView">
{cust_body}</div>

<div id="adminView" hidden>
{admin_body}</div>

<div class="toast" id="toast" hidden></div>

<script>
{store}</script>
<script>
{cust_js}</script>
<script>
{admin_js}</script>
<script>
(() => {{
  const KEY = "yuki-demo-view";
  function show(v){{
    document.getElementById("custView").hidden = v !== "cust";
    document.getElementById("adminView").hidden = v !== "admin";
    document.querySelectorAll(".switcher [data-view]").forEach(b => b.setAttribute("aria-pressed", b.dataset.view === v));
    try {{ localStorage.setItem(KEY, v); }} catch {{}}
    window.scrollTo(0, 0);
  }}
  document.addEventListener("click", e => {{
    const b = e.target.closest("[data-view]"); if (b) show(b.dataset.view);
  }});
  let v = location.hash === "#admin" ? "admin" : "cust";
  try {{ if (!location.hash) v = localStorage.getItem(KEY) || v; }} catch {{}}
  show(v);
  // 切り替えバーの高さぶん、各画面のヘッダーを下げる
  const sw = document.querySelector(".switcher");
  const fit = () => document.documentElement.style.setProperty("--swh", sw.offsetHeight + "px");
  fit(); addEventListener("resize", fit);
}})();
</script>
</body>
</html>
"""
(HERE / "demo.html").write_text(page, encoding="utf-8")
print("wrote", HERE / "demo.html", len(page), "bytes")
