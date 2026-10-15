"""店舗情報ファイル（client.toml）の読み込みと入力チェック。"""
import tomllib
from pathlib import Path

PLACEHOLDER_NAMES = {"サロン名", "地域名", "メニュー名"}


class ConfigError(Exception):
    pass


def load_client(path):
    path = Path(path)
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"店舗情報ファイルが見つかりません: {path}")
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path} の書き方に誤りがあります（\" の閉じ忘れ等）: {e}")

    salon = data.setdefault("salon", {})
    salon.setdefault("tone", "やさしい")
    salon.setdefault("use_emoji", True)
    salon.setdefault("reservation", "プロフィールのリンクからご予約いただけます")
    for key in ("name", "business_type", "area", "access", "concept", "target"):
        salon.setdefault(key, "")
    salon.setdefault("features", [])
    salon.setdefault("first_visit_flow", [])
    salon.setdefault("sample", False)

    data.setdefault("menus", [])
    for m in data["menus"]:
        for key in ("name", "duration", "price", "description"):
            m.setdefault(key, "")
        m.setdefault("concerns", [])
    data["menus"] = [m for m in data["menus"] if m["name"].strip()]
    data.setdefault("faqs", [])
    data["faqs"] = [q for q in data["faqs"] if q.get("q") and q.get("a")]
    data.setdefault("staff", [])
    data["staff"] = [s for s in data["staff"] if s.get("name")]

    tags = data.setdefault("hashtags", {})
    tags.setdefault("max", 5)
    tags.setdefault("keywords", [])
    tags.setdefault("custom", [])
    priv = data.setdefault("privacy", {})
    priv.setdefault("photo_consent", False)
    priv.setdefault("ng_words", [])
    return data


def validate(data):
    """生成を止めるべき問題（エラー）のリストを返す。"""
    errors = []
    s = data["salon"]
    if not s["name"].strip() or s["name"] in PLACEHOLDER_NAMES:
        errors.append("[salon] name（サロン名）を入力してください")
    if not data["menus"] or all(m["name"] in PLACEHOLDER_NAMES for m in data["menus"]):
        errors.append("[[menus]] を1つ以上入力してください（name は必須）")
    if s["tone"] not in ("やさしい", "上品", "親しみ"):
        errors.append("tone は「やさしい」「上品」「親しみ」のどれかにしてください")
    return errors
