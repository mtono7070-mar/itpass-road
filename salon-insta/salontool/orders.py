"""顧客フォルダ・注文（制作案件）の保存、チェック、納品データ作成、状況管理。"""
import csv
import datetime as dt
import json
import re
import shutil
from pathlib import Path

from . import checker
from .config import load_client
from .generator import PLAN_LABELS

COLUMNS = ["番号", "投稿予定日", "投稿タイプ", "テーマ", "見出し", "サブ見出し", "画像構成案",
           "キャプション", "ハッシュタグ", "要確認事項", "警告", "人間確認", "確認メモ"]
CHECK_FIELDS = ["見出し", "サブ見出し", "画像構成案", "キャプション", "ハッシュタグ"]
STATUSES = ["下書き作成済", "自己確認中", "納品データ作成済", "顧客確認待ち", "修正中", "納品済", "入金確認済"]
OVERRIDE_MARK = "表現確認済"

PHOTO_README = """このフォルダに店舗から受け取った写真を保存します。

・写真は GitHub やクラウドの公開フォルダに上げない（.gitignore で除外済み）
・使用許諾（どの投稿に使ってよいか）を店舗に確認する
・お客様やスタッフが写っている写真は、本人の掲載同意を確認する
・ファイル名に個人名を入れない（例：menu_facial_01.jpg）
・契約終了後は、店舗と決めた期間で削除する
"""


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def client_dir(root, cid):
    return Path(root) / "clients" / cid


def create_client(root, cid, template):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", cid):
        raise ValueError("顧客IDは半角英数字・ハイフン・アンダーバーで指定してください（例：salon-a）")
    d = client_dir(root, cid)
    if d.exists():
        raise FileExistsError(f"{d} はすでにあります")
    (d / "photos").mkdir(parents=True)
    (d / "orders").mkdir()
    shutil.copy(template, d / "client.toml")
    (d / "photos" / "README.txt").write_text(PHOTO_README, encoding="utf-8")
    return d


def write_posts(path, posts):
    # Excel で文字化けしないよう BOM 付き UTF-8
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for p in posts:
            w.writerow({k: p.get(k, "") for k in COLUMNS})


def read_posts(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: (row.get(k) or "") for k in COLUMNS} for row in csv.DictReader(f)]


def load_status(order_dir):
    return json.loads((order_dir / "status.json").read_text(encoding="utf-8"))


def save_status(order_dir, st):
    (order_dir / "status.json").write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def set_status(order_dir, status, note=""):
    if status not in STATUSES:
        raise ValueError("状態は次のどれかです：" + " / ".join(STATUSES))
    if STATUSES.index(status) > STATUSES.index("納品データ作成済") and status != "修正中" \
            and not (order_dir / "納品").exists():
        raise ValueError("まだ納品データがありません。先に deliver で人間確認済みの納品データを作ってください")
    st = load_status(order_dir)
    st["status"] = status
    st["updated"] = now()
    st["history"].append({"at": st["updated"], "status": status, "note": note})
    save_status(order_dir, st)


def new_order(root, cid, plan, posts):
    d = client_dir(root, cid) / "orders"
    base = dt.date.today().strftime("%Y%m%d") + "-" + plan
    oid, n = base, 2
    while (d / oid).exists():
        oid, n = f"{base}-{n}", n + 1
    od = d / oid
    od.mkdir(parents=True)
    write_posts(od / "posts.csv", posts)
    save_status(od, {"client": cid, "order": oid, "plan": plan, "status": "下書き作成済",
                     "created": now(), "updated": now(),
                     "history": [{"at": now(), "status": "下書き作成済", "note": "自動生成"}]})
    return od


def count_orders(root, cid):
    d = client_dir(root, cid) / "orders"
    return len([p for p in d.iterdir() if p.is_dir()]) if d.exists() else 0


def run_check(order_dir, data):
    """posts.csv の警告列を更新し、確認用 Markdown を作り直す。集計を返す。"""
    posts = read_posts(order_dir / "posts.csv")
    ng_words = data["privacy"]["ng_words"]
    summary = {"posts": len(posts), "ng": 0, "caution": 0, "approved": 0, "blocked": []}
    for p in posts:
        text = "\n".join(p[k] for k in CHECK_FIELDS)
        ws = checker.check_text(text, ng_words)
        p["警告"] = checker.format_warnings(ws)
        ng = checker.count_level(ws, checker.NG)
        summary["ng"] += ng
        summary["caution"] += checker.count_level(ws, checker.CAUTION)
        approved = p["人間確認"].strip() in ("済", "OK", "ok", "確認済")
        summary["approved"] += approved
        reasons = []
        if not approved:
            reasons.append("人間確認が「済」になっていない")
        if ng and OVERRIDE_MARK not in p["確認メモ"]:
            reasons.append(f"NG表現が{ng}件ある（書き換えるか、確認メモに「{OVERRIDE_MARK}：理由」を記入）")
        if "【要確認" in text:
            reasons.append("【要確認】が本文に残っている")
        if reasons:
            summary["blocked"].append((p["番号"], reasons))
    write_posts(order_dir / "posts.csv", posts)
    (order_dir / "確認用.md").write_text(render_review(posts, data, load_status(order_dir)), encoding="utf-8")
    return summary


def render_review(posts, data, st):
    out = [f"# 確認用：{data['salon']['name']}（{st['order']}）", "",
           "> 社内確認用です。そのまま店舗に送らないでください。警告は機械的な注意喚起で、法的判断ではありません。", ""]
    for p in posts:
        out += [f"## {p['番号']}. {p['見出し']}（{p['投稿タイプ']}・{p['投稿予定日']}）", "",
                f"- 人間確認：**{p['人間確認'] or '未'}**", f"- テーマ：{p['テーマ']}", ""]
        if p["警告"]:
            out += ["### ⚠ 表現チェック", ""] + [f"- {l}" for l in p["警告"].splitlines()] + [""]
        if p["要確認事項"]:
            out += ["### 要確認事項", ""] + [f"- [ ] {l}" for l in p["要確認事項"].splitlines()] + [""]
        out += _post_body(p)
    return "\n".join(out)


def _post_body(p):
    return (["### 画像構成案", ""] + [f"- {l}" for l in p["画像構成案"].splitlines()] + [""] +
            ["### キャプション", "", "```text", p["キャプション"], "```", "",
             "### ハッシュタグ", "", "```text", p["ハッシュタグ"], "```", ""])


def deliver(order_dir, data):
    """全投稿が確認済みのときだけ納品フォルダを作る。作れなければ理由を返す。"""
    summary = run_check(order_dir, data)
    if summary["blocked"]:
        return None, summary
    posts = read_posts(order_dir / "posts.csv")
    st = load_status(order_dir)
    out = order_dir / "納品"
    out.mkdir(exist_ok=True)
    public = ["番号", "投稿予定日", "投稿タイプ", "見出し", "サブ見出し", "画像構成案", "キャプション", "ハッシュタグ"]
    with open(out / "投稿一覧.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=public, extrasaction="ignore")
        w.writeheader()
        w.writerows(posts)
    _write_canva(out / "canva一括作成用.csv", posts)
    (out / "納品資料.md").write_text(render_delivery(posts, data, st), encoding="utf-8")
    report = [f"# チェック記録（{st['order']}）", "", f"作成日時：{now()}", ""]
    for p in posts:
        report.append(f"- {p['番号']}. {p['見出し']}：人間確認={p['人間確認']} / 確認メモ={p['確認メモ'] or 'なし'}")
        report += [f"  - {l}" for l in p["警告"].splitlines()]
    (order_dir / "チェック記録.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    set_status(order_dir, "納品データ作成済", "deliver 実行")
    return out, summary


def _write_canva(path, posts):
    """Canva の一括作成（Bulk Create）に読み込める形。1行=1投稿、列=各スライドの文字。"""
    rows, maxn = [], 0
    for p in posts:
        texts = re.findall(r"文字：(.*?)｜素材", p["画像構成案"])
        maxn = max(maxn, len(texts))
        rows.append((p, texts))
    cols = ["番号", "見出し", "サブ見出し"] + [f"スライド{i}" for i in range(1, maxn + 1)]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for p, texts in rows:
            w.writerow([p["番号"], p["見出し"], p["サブ見出し"]] + texts + [""] * (maxn - len(texts)))


def render_delivery(posts, data, st):
    s = data["salon"]
    out = [f"# {s['name']} 様　Instagram投稿案", "",
           f"- プラン：{PLAN_LABELS.get(st['plan'], st['plan'])}　/　投稿数：{len(posts)}本", "",
           "## ご確認のお願い", "",
           "- 投稿前に、内容・料金・表現が実際のサービスと合っているかご確認ください。",
           "- 投稿の公開は店舗様のご判断で行ってください（制作者が代理で投稿することはありません）。",
           "- 写真は店舗様からご提供いただいたもの、または使用許諾のある素材のみを使用します。", ""]
    confirms = {}  # 同じ確認事項は1行にまとめる
    for p in posts:
        for line in filter(None, p["要確認事項"].splitlines()):
            confirms.setdefault(line, []).append(p["番号"])
    if confirms:
        out += ["## 店舗様にご確認いただきたい点", ""]
        out += [f"- [ ] 投稿{'・'.join(ns)}：{line}" for line, ns in confirms.items()] + [""]
    for p in posts:
        out += [f"## 投稿{p['番号']}：{p['見出し']}", "", f"- 投稿予定日：{p['投稿予定日']}", f"- 種類：{p['投稿タイプ']}", ""]
        out += _post_body(p)
    return "\n".join(out)


def list_orders(root):
    rows = []
    base = Path(root) / "clients"
    for sf in sorted(base.glob("*/orders/*/status.json")):
        st = json.loads(sf.read_text(encoding="utf-8"))
        posts = read_posts(sf.parent / "posts.csv")
        approved = sum(p["人間確認"].strip() in ("済", "OK", "ok", "確認済") for p in posts)
        ng = sum(l.startswith("[NG]") for p in posts for l in p["警告"].splitlines())
        rows.append({"顧客": st["client"], "注文": st["order"], "プラン": st["plan"], "投稿数": len(posts),
                     "確認済": f"{approved}/{len(posts)}", "NG": ng, "状態": st["status"], "更新": st["updated"]})
    return rows


def find_order(root, cid, oid=None):
    d = client_dir(root, cid) / "orders"
    if not d.exists():
        raise FileNotFoundError(f"顧客 {cid} が見つかりません")
    if oid:
        od = d / oid
        if not od.exists():
            raise FileNotFoundError(f"注文 {oid} が見つかりません")
        return od
    orders = sorted((p for p in d.iterdir() if (p / "status.json").exists()),
                    key=lambda p: (load_status(p)["created"], p.stat().st_mtime))
    if not orders:
        raise FileNotFoundError(f"{cid} の注文がまだありません（generate を実行してください）")
    return orders[-1]


def load_client_of(root, cid):
    return load_client(client_dir(root, cid) / "client.toml")
