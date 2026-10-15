#!/usr/bin/env python3
"""サロン向け Instagram 投稿制作ツール（操作は README.md を参照）。

使い方の例:
  python3 salon.py sample                     架空サロンのサンプルを作る
  python3 salon.py new-client salon-a         顧客フォルダを作る
  python3 salon.py generate salon-a --plan trial
  python3 salon.py check salon-a
  python3 salon.py deliver salon-a
  python3 salon.py status
"""
import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

from salontool import orders
from salontool.config import ConfigError, load_client, validate
from salontool.generator import PLAN_COUNTS, PLAN_LABELS, generate

ROOT = Path(__file__).resolve().parent
SAMPLE_ID = "sample-salon"


def next_monday():
    d = dt.date.today() + dt.timedelta(days=1)
    return d + dt.timedelta(days=(7 - d.weekday()) % 7)


def print_summary(od, s):
    print(f"\n対象：{od}")
    print(f"投稿 {s['posts']} 本 / 人間確認済 {s['approved']} 本 / NG {s['ng']} 件 / 注意 {s['caution']} 件")
    if s["blocked"]:
        print("\n納品前に対応が必要な投稿：")
        for n, reasons in s["blocked"]:
            for r in reasons:
                print(f"  投稿{n}：{r}")


def cmd_new_client(a):
    d = orders.create_client(ROOT, a.client, ROOT / "templates" / "client_template.toml")
    print(f"顧客フォルダを作りました：{d}")
    print(f"次に {d / 'client.toml'} を開いて店舗情報を入力してください。")


def cmd_generate(a):
    data = orders.load_client_of(ROOT, a.client)
    errs = validate(data)
    if errs:
        print("店舗情報ファイルを修正してください：\n  " + "\n  ".join(errs))
        return 1
    start = dt.date.fromisoformat(a.start) if a.start else next_monday()
    count = a.count or PLAN_COUNTS[a.plan]
    offset = orders.count_orders(ROOT, a.client)
    posts = generate(data, count, start, seed=f"{a.client}-{offset}", offset=offset)
    od = orders.new_order(ROOT, a.client, a.plan, posts)
    s = orders.run_check(od, data)
    print(f"{PLAN_LABELS[a.plan]} の下書きを作りました。")
    print_summary(od, s)
    print(f"\n次の作業：{od / '確認用.md'} を読み、{od / 'posts.csv'} を修正して「人間確認」を「済」にする")
    return 0


def cmd_check(a):
    od = orders.find_order(ROOT, a.client, a.order)
    data = orders.load_client_of(ROOT, a.client)
    s = orders.run_check(od, data)
    if orders.load_status(od)["status"] == "下書き作成済":
        orders.set_status(od, "自己確認中", "check 実行")
    print_summary(od, s)
    print(f"\n確認用ファイルを更新しました：{od / '確認用.md'}")
    return 0


def cmd_deliver(a):
    od = orders.find_order(ROOT, a.client, a.order)
    data = orders.load_client_of(ROOT, a.client)
    out, s = orders.deliver(od, data)
    print_summary(od, s)
    if out is None:
        print("\n納品データは作成していません。上の項目を対応してから再実行してください。")
        return 1
    print(f"\n納品データを作りました：{out}")
    print("  投稿一覧.csv / 納品資料.md / canva一括作成用.csv")
    print("店舗に送ったら：python3 salon.py set-status", a.client, "顧客確認待ち")
    return 0


def cmd_status(a):
    rows = orders.list_orders(ROOT)
    if not rows:
        print("まだ注文がありません。")
        return 0
    cols = list(rows[0])
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    table = "\n".join(lines)
    print(table)
    (ROOT / "clients" / "制作状況.md").write_text(f"# 制作状況（{orders.now()} 時点）\n\n{table}\n", encoding="utf-8")
    return 0


def cmd_set_status(a):
    od = orders.find_order(ROOT, a.client, a.order)
    orders.set_status(od, a.status, a.note or "")
    print(f"{od.name} の状態を「{a.status}」にしました。")
    return 0


def cmd_sample(a):
    d = orders.client_dir(ROOT, SAMPLE_ID)
    if d.exists():
        shutil.rmtree(d)
    orders.create_client(ROOT, SAMPLE_ID, ROOT / "samples" / "sample_salon.toml")
    a.client, a.plan, a.order = SAMPLE_ID, "sample", None
    data = load_client(d / "client.toml")
    start = dt.date.fromisoformat(a.start) if a.start else next_monday()
    posts = generate(data, a.count, start, seed=SAMPLE_ID)
    od = orders.new_order(ROOT, SAMPLE_ID, "sample", posts)
    s = orders.run_check(od, data)
    print(f"架空サロンのサンプル投稿を {a.count} 本作りました。")
    print_summary(od, s)
    print(f"\n確認用：{od / '確認用.md'}")
    return 0


def cmd_prompt(a):
    """Claude（claude.ai等、契約済みのもの）に貼り付けて文章を整えるための依頼文を作る。"""
    od = orders.find_order(ROOT, a.client, a.order)
    posts = orders.read_posts(od / "posts.csv")
    body = "\n\n".join(f"--- 投稿{p['番号']}（{p['投稿タイプ']}）---\n見出し：{p['見出し']}\n{p['キャプション']}" for p in posts)
    text = f"""以下はエステ・美容サロンのInstagram投稿キャプションの下書きです。読みやすく自然な日本語に整えてください。

守ること：
- 下書きにない事実（施術効果、料金、口コミ、実績、数値、キャンペーン）を追加しない
- 「治る」「消える」「痩せる」「若返る」「必ず」「No.1」など、効果の断定・保証・最上級表現を使わない
- 店舗名・メニュー名・所要時間・料金・予約方法は変更しない
- 各投稿を「投稿番号／見出し／キャプション」の形で返す

{body}
"""
    path = od / "整文用プロンプト.txt"
    path.write_text(text, encoding="utf-8")
    print(f"作成しました：{path}")
    print("中身をClaudeに貼り付け、返ってきた文章をposts.csvに反映したら check を実行してください。")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="サロン向けInstagram投稿制作ツール")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new-client", help="顧客フォルダを作る")
    s.add_argument("client")
    s.set_defaults(func=cmd_new_client)

    s = sub.add_parser("generate", help="投稿案を一括生成する")
    s.add_argument("client")
    s.add_argument("--plan", choices=["trial", "monthly"], default="trial")
    s.add_argument("--count", type=int, help="投稿数を手動指定（省略時はプランどおり）")
    s.add_argument("--start", help="最初の投稿予定日 YYYY-MM-DD（省略時は次の月曜）")
    s.set_defaults(func=cmd_generate)

    for name, func, h in [("check", cmd_check, "表現チェックと確認用ファイルの更新"),
                          ("deliver", cmd_deliver, "納品データを作る（全投稿確認済みのときのみ）"),
                          ("prompt", cmd_prompt, "Claudeで文章を整えるための依頼文を作る")]:
        s = sub.add_parser(name, help=h)
        s.add_argument("client")
        s.add_argument("order", nargs="?", help="注文ID（省略時は最新）")
        s.set_defaults(func=func)

    s = sub.add_parser("status", help="全顧客の制作状況を一覧表示")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("set-status", help="注文の状態を変える")
    s.add_argument("client")
    s.add_argument("status", choices=orders.STATUSES)
    s.add_argument("--order", help="注文ID（省略時は最新）")
    s.add_argument("--note", help="メモ")
    s.set_defaults(func=cmd_set_status)

    s = sub.add_parser("sample", help="架空サロンのサンプル投稿を作る")
    s.add_argument("--count", type=int, default=6)
    s.add_argument("--start")
    s.set_defaults(func=cmd_sample)

    a = p.parse_args(argv)
    try:
        return a.func(a) or 0
    except (ConfigError, FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"エラー：{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
