"""店舗情報から投稿案（テーマ・見出し・画像構成・キャプション・ハッシュタグ）を作る。

方針：
- 店舗情報ファイルに書かれた事実だけを使う。効果・料金・口コミ・実績は作らない。
- 足りない情報は「要確認」に書き出し、人間が確認・追記する。
"""
import datetime as dt
import random
import re

PLAN_COUNTS = {"trial": 4, "monthly": 8}
PLAN_LABELS = {"trial": "お試し（4投稿）", "monthly": "継続（月8投稿）", "sample": "サンプル"}

TONES = {
    "やさしい": {"closing": "ご予約・ご相談をお待ちしております{e}", "e": "🌿"},
    "上品": {"closing": "ご来店を心よりお待ちしております{e}", "e": "✨"},
    "親しみ": {"closing": "気軽にご相談くださいね{e}", "e": "😊"},
}

# 季節の話題（医療的・効果断定でない一般的なお手入れの意識づけのみ）
SEASONS = {
    1: ("冬の乾燥", "空気が乾燥しやすい季節", ["室内の湿度にも気を配る", "洗顔はこすらずやさしく", "保湿のお手入れを丁寧に"]),
    2: ("季節の変わり目の準備", "寒さと乾燥が続く季節", ["保湿のお手入れを丁寧に", "首元・手元のお手入れも忘れずに", "睡眠時間を意識する"]),
    3: ("春のゆらぎ", "環境が変わりやすい季節", ["新しいアイテムは少しずつ試す", "紫外線対策を始める", "気になることは早めに相談"]),
    4: ("新生活のセルフケア", "新生活で忙しくなりやすい季節", ["自分のための時間をつくる", "紫外線対策を習慣に", "無理のないお手入れを続ける"]),
    5: ("紫外線が気になる季節", "日差しが強くなり始める季節", ["日焼け止めをこまめに塗り直す", "帽子や日傘も活用", "帰宅後はやさしく洗う"]),
    6: ("梅雨のお手入れ", "湿気が多い季節", ["汗や皮脂はこまめにオフ", "保湿も忘れずに", "ジメジメ時期はリラックス時間を"]),
    7: ("夏の日差し対策", "紫外線が強い季節", ["日焼け止めの塗り直し", "冷房による乾燥にも注意", "水分補給を意識"]),
    8: ("夏の疲れが気になる時期", "暑さが続く季節", ["冷房で冷えすぎない工夫", "保湿のお手入れを見直す", "ゆっくり休む時間をつくる"]),
    9: ("夏から秋へのお手入れ", "季節の変わり目", ["夏に頑張った肌をいたわる", "保湿を少しずつ強化", "生活リズムを整える"]),
    10: ("秋の乾燥対策", "乾燥が気になり始める季節", ["保湿のお手入れを見直す", "洗顔後は早めに保湿", "首元・手元のケアも"]),
    11: ("冬に向けた準備", "空気が乾燥し始める季節", ["室内の湿度にも気を配る", "こすらないやさしい洗顔", "保湿のお手入れを丁寧に"]),
    12: ("年末のご褒美ケア", "忙しくなりやすい年末", ["自分のための時間をつくる", "乾燥対策を続ける", "1年頑張った自分をいたわる"]),
}


class Writer:
    def __init__(self, data, seed):
        self.d = data
        self.s = data["salon"]
        self.rng = random.Random(seed)
        t = TONES[self.s["tone"]]
        self.e = t["e"] if self.s["use_emoji"] else ""
        self.closing = t["closing"].format(e=self.e)

    def pick(self, options):
        return self.rng.choice(options)

    def footer(self):
        lines = [f"{'📍' if self.e else '■'}{self.s['name']}"]
        if self.s["access"]:
            lines.append(self.s["access"])
        if self.s["features"]:
            lines.append("・".join(self.s["features"]))
        if self.s.get("sample"):
            lines.append("※架空サロンのサンプル投稿です")
        return "\n".join(lines)

    def ending(self):
        return f"{self.s['reservation']}\n{self.closing}\n\n{self.footer()}"

    def price_text(self, menu, confirm):
        if menu["price"]:
            return menu["price"]
        confirm.append(f"「{menu['name']}」の料金が未入力のため投稿に載せていません（載せる場合は店舗に確認）")
        return ""

    def menu_desc(self, menu, confirm):
        if menu["description"]:
            return menu["description"]
        confirm.append(f"「{menu['name']}」の説明が未入力です（店舗にメニュー内容を確認）")
        return "【要確認：メニューの説明】"

    # ---- 投稿タイプごとの作成 ----
    def post_menu(self, menu):
        c = []
        desc = self.menu_desc(menu, c)
        price = self.price_text(menu, c)
        title = self.pick([f"メニュー紹介｜{menu['name']}", f"{menu['name']}のご案内", f"はじめての方へ｜{menu['name']}"])
        sub = f"所要時間 {menu['duration']}" if menu["duration"] else self.s["name"]
        detail = "\n".join(x for x in [menu["duration"] and f"■所要時間：{menu['duration']}",
                                      price and f"■料金：{price}"] if x)
        recommend = "\n".join(f"・{x}が気になる方" for x in menu["concerns"])
        slides = [(title, "施術イメージ or 店内の写真（店舗提供）"),
                  ("こんな方におすすめ\n" + recommend if recommend else "メニューの特徴\n" + desc, "やわらかい色の背景＋テキスト"),
                  ("メニュー内容\n" + desc, "施術中の手元写真（店舗提供・顔が写らないもの）"),
                  ((detail or "詳しくはプロフィールのリンクから").replace("■", ""), "シンプルな背景＋テキスト"),
                  ("ご予約はプロフィールのリンクから", "ロゴ or 店内写真")]
        cap = f"{menu['name']}のご案内です{self.e}\n\n{desc}\n"
        if recommend:
            cap += f"\nこんな方におすすめです\n{recommend}\n"
        if detail:
            cap += f"\n{detail}\n"
        cap += "\n" + self.ending()
        return dict(type="メニュー紹介", theme=f"メニュー紹介：{menu['name']}", headline=title, subhead=sub,
                    slides=slides, caption=cap, confirm=c, tags_from=[menu["name"]])

    def post_worry(self, menu, concern):
        c = []
        desc = self.menu_desc(menu, c)
        title = self.pick([f"{concern}が気になる方へ", f"{concern}、気になっていませんか？"])
        slides = [(title, "季節感のある写真 or 店内写真（店舗提供）"),
                  (f"こんなお悩みありませんか？\n・{concern}が気になる", "テキスト中心のデザイン"),
                  (f"{self.s['name']}の{menu['name']}\n{desc}", "施術イメージ写真（店舗提供）"),
                  ("まずはご相談ください\n※感じ方には個人差があります", "ロゴ or 店内写真")]
        cap = (f"「{concern}が気になる」と感じている方へ{self.e}\n\n"
               f"{self.s['name']}では、{menu['name']}をご用意しています。\n{desc}\n\n"
               f"肌や体の状態をうかがいながら、内容をご相談して進めます。\n"
               f"※感じ方には個人差があります。\n\n" + self.ending())
        return dict(type="お悩み別提案", theme=f"お悩み：{concern} → {menu['name']}", headline=title,
                    subhead=menu["name"], slides=slides, caption=cap, confirm=c, tags_from=[menu["name"]])

    def post_salon(self):
        c = []
        s = self.s
        concept = s["concept"] or "【要確認：お店のコンセプト】"
        if not s["concept"]:
            c.append("コンセプトが未入力です（店舗が大切にしていることを確認）")
        if not s["features"]:
            c.append("お店の特徴が未入力です（掲載したい特徴を確認）")
        title = self.pick([f"{s['name']}ってどんなサロン？", f"はじめまして、{s['name']}です"])
        slides = [(title, "外観 or 店内写真（店舗提供）"), ("大切にしていること\n" + concept, "店内の雰囲気写真")]
        for f in s["features"][:3]:
            slides.append((f, "特徴が伝わる写真（店舗提供）"))
        slides.append(("アクセス\n" + (s["access"] or "プロフィールをご覧ください"), "地図イラスト or 外観"))
        feats = "\n".join(f"・{f}" for f in s["features"])
        cap = f"{title}{self.e}\n\n{concept}\n"
        if feats:
            cap += f"\n{feats}\n"
        if s["target"]:
            cap += f"\n{s['target']}の方にも通っていただきやすいよう、心地よい空間づくりを心がけています。\n"
            c.append("「心地よい空間づくりを心がけています」の一文が店舗の考えと合っているか確認")
        cap += "\n" + self.ending()
        return dict(type="サロン紹介", theme="サロンの雰囲気・特徴", headline=title, subhead=s["area"] or "",
                    slides=slides, caption=cap, confirm=c, tags_from=[])

    def post_flow(self):
        c = []
        steps = self.s["first_visit_flow"]
        if not steps:
            steps = ["ご予約", "カウンセリング", "施術", "お会計・次回のご相談"]
            c.append("来店の流れが未入力のため一般的な流れにしています（実際の流れと合うか確認）")
        title = "はじめての方へ｜ご来店の流れ"
        slides = [(title, "店内 or 受付の写真（店舗提供）")]
        slides += [(f"STEP{i}\n{st}", "各ステップがイメージできる写真 or アイコン") for i, st in enumerate(steps, 1)]
        flow = "\n".join(f"{i}. {st}" for i, st in enumerate(steps, 1))
        cap = (f"はじめてご来店される方へ、当日の流れをご紹介します{self.e}\n\n{flow}\n\n"
               f"分からないことがあれば、ご予約前でもお気軽にお問い合わせください。\n\n" + self.ending())
        return dict(type="はじめての方へ", theme="ご来店の流れ", headline=title, subhead=self.s["name"],
                    slides=slides, caption=cap, confirm=c, tags_from=[])

    def post_faq(self, faqs):
        title = self.pick(["よくあるご質問", "Q&A｜よくいただくご質問"])
        slides = [(title, "テキスト中心のデザイン")]
        slides += [(f"Q. {f['q']}\nA. {f['a']}", "Q&A形式のデザイン") for f in faqs[:3]]
        qa = "\n\n".join(f"Q. {f['q']}\nA. {f['a']}" for f in faqs[:3])
        cap = f"よくいただくご質問をまとめました{self.e}\n\n{qa}\n\nほかにも気になることがあればお気軽にどうぞ。\n\n" + self.ending()
        return dict(type="よくある質問", theme="FAQ", headline=title, subhead=self.s["name"],
                    slides=slides, caption=cap, confirm=[], tags_from=[])

    def post_season(self, month, menu):
        theme, lead, points = SEASONS[month]
        title = f"{month}月｜{theme}"
        pts = "\n".join(f"・{p}" for p in points)
        slides = [(title, "季節を感じる写真 or 素材（Canva素材可）"), (lead, "季節のイラスト"),
                  ("意識したいポイント\n" + pts, "テキスト中心のデザイン"),
                  (f"サロンでは\n{menu['name']}をご用意しています", "施術イメージ写真（店舗提供）")]
        cap = (f"{lead}になりました{self.e}\n\n日々のお手入れで意識したいポイント\n{pts}\n\n"
               f"{self.s['name']}では{menu['name']}をご用意しています。気になることはお気軽にご相談ください。\n\n"
               + self.ending())
        return dict(type="季節のお手入れ", theme=f"{month}月の季節テーマ：{theme}", headline=title, subhead=self.s["name"],
                    slides=slides, caption=cap, tags_from=[menu["name"]],
                    confirm=["季節のポイントが店舗の考え方と合っているか確認"])

    def post_staff(self, st):
        title = f"スタッフ紹介｜{st['name']}"
        msg = st.get("message", "")
        slides = [(title, "スタッフ写真（本人の掲載同意済みのもの）"),
                  (f"{st.get('role', '')}\n{st['name']}", "スタッフ写真 or イラスト")]
        if msg:
            slides.append(("メッセージ\n" + msg, "テキスト中心のデザイン"))
        cap = f"スタッフをご紹介します{self.e}\n\n{st.get('role', '')} {st['name']}\n"
        if msg:
            cap += f"\n「{msg}」\n"
        cap += "\n" + self.ending()
        return dict(type="スタッフ紹介", theme=f"スタッフ紹介：{st['name']}", headline=title, subhead=st.get("role", ""),
                    slides=slides, caption=cap, tags_from=[],
                    confirm=[f"{st['name']}さんの写真・名前の掲載同意を確認"])

    def post_reserve(self):
        title = "ご予約のご案内"
        slides = [(title, "店内写真（店舗提供）"), ("ご予約方法\n" + self.s["reservation"], "テキスト中心のデザイン"),
                  ("ご不明点はお気軽にご相談ください", "ロゴ or 店内写真")]
        cap = f"ご予約方法のご案内です{self.e}\n\n{self.s['reservation']}\n\n{self.closing}\n\n{self.footer()}"
        return dict(type="予約案内", theme="予約方法の案内", headline=title, subhead=self.s["name"], slides=slides,
                    caption=cap, tags_from=[], confirm=["空き状況を載せる場合は、投稿直前の最新情報を店舗に確認"])


def candidate_posts(w, data, month, offset=0):
    """優先順位の高い順に、作れる投稿を並べる。offset で月ごとにメニューをずらす。"""
    menus = data["menus"]
    n = len(menus)
    menus = menus[offset % n:] + menus[:offset % n]
    worries = [(m, c) for m in menus for c in m["concerns"]]
    seq = [lambda: w.post_menu(menus[0])]
    if worries:
        seq.append(lambda: w.post_worry(*worries[0]))
    seq.append(lambda: w.post_salon())
    seq.append((lambda: w.post_faq(data["faqs"])) if data["faqs"] else (lambda: w.post_season(month, menus[0])))
    for m in menus[1:]:
        seq.append(lambda m=m: w.post_menu(m))
    seq.append(lambda: w.post_flow())
    if data["faqs"]:
        seq.append(lambda: w.post_season(month, menus[0]))
    for st in data["staff"]:
        seq.append(lambda st=st: w.post_staff(st))
    for m, c in worries[1:]:
        seq.append(lambda m=m, c=c: w.post_worry(m, c))
    seq.append(lambda: w.post_reserve())
    return seq


def hashtags(data, post):
    s, cfg = data["salon"], data["hashtags"]
    area = "" if s["area"] in ("", "地域名") else s["area"]
    tags = []
    for kw in cfg["keywords"]:
        tags.append(f"{area}{kw}" if area else kw)
    for word in post["tags_from"]:
        tags.append(word)
    tags += cfg["custom"]
    if area:
        tags.append(f"{area}サロン")
    clean, seen = [], set()
    for t in tags:
        t = re.sub(r"[\s・、。,.!！?？()（）「」『』#＃&＆/／]+", "", t)
        if t and t not in seen:
            seen.add(t)
            clean.append("#" + t)
    return clean[: int(cfg["max"])]


def schedule(start, count):
    """週2回（開始日・3日後）のペースで投稿予定日を並べる。"""
    days = []
    week = 0
    while len(days) < count:
        for off in (0, 3):
            if len(days) < count:
                days.append(start + dt.timedelta(days=week * 7 + off))
        week += 1
    return days


def slides_text(slides):
    return "\n".join(f"{i}枚目｜文字：{t.replace(chr(10), ' / ')}｜素材：{v}" for i, (t, v) in enumerate(slides, 1))


def generate(data, count, start, seed="", offset=0):
    w = Writer(data, seed)
    month = start.month
    seq = candidate_posts(w, data, month, offset)
    posts = []
    days = schedule(start, count)
    for i in range(count):
        p = seq[i % len(seq)]()
        if not data["privacy"]["photo_consent"]:
            p["confirm"].append("写真の使用許諾・写り込んだ人物の掲載同意が未確認です")
        posts.append({
            "番号": str(i + 1),
            "投稿予定日": days[i].isoformat(),
            "投稿タイプ": p["type"],
            "テーマ": p["theme"],
            "見出し": p["headline"],
            "サブ見出し": p["subhead"],
            "画像構成案": slides_text(p["slides"]),
            "キャプション": p["caption"],
            "ハッシュタグ": " ".join(hashtags(data, p)),
            "要確認事項": "\n".join(dict.fromkeys(p["confirm"])),
            "警告": "",
            "人間確認": "未",
            "確認メモ": "",
        })
    return posts
