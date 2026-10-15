import datetime as dt
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from salontool import checker, orders  # noqa: E402
from salontool.config import load_client, validate  # noqa: E402
from salontool.generator import generate  # noqa: E402

SAMPLE = ROOT / "samples" / "sample_salon.toml"
TEMPLATE = ROOT / "templates" / "client_template.toml"


class CheckerTest(unittest.TestCase):
    def test_ng_expressions(self):
        for text in ["シミが消える", "ニキビが治る", "必ず痩せる", "若返り効果", "永久脱毛", "細胞を活性化"]:
            ws = checker.check_text(text)
            self.assertTrue(any(w.level == checker.NG for w in ws), text)

    def test_caution_expressions(self):
        for text in ["地域No.1", "満足度98%", "お客様の声", "今だけ半額", "業界最安"]:
            ws = checker.check_text(text)
            self.assertTrue(ws, text)

    def test_safe_text(self):
        self.assertEqual(checker.check_text("乾燥が気になる方へ。保湿フェイシャルのご案内です。"), [])

    def test_salon_ng_words(self):
        ws = checker.check_text("お得なプラン", ["お得"])
        self.assertEqual(ws[0].level, checker.NG)


class GeneratorTest(unittest.TestCase):
    def setUp(self):
        self.data = load_client(SAMPLE)

    def test_counts_and_dates(self):
        posts = generate(self.data, 4, dt.date(2026, 11, 2))
        self.assertEqual(len(posts), 4)
        self.assertEqual([p["投稿予定日"] for p in posts], ["2026-11-02", "2026-11-05", "2026-11-09", "2026-11-12"])
        self.assertEqual(len(generate(self.data, 8, dt.date(2026, 11, 2))), 8)

    def test_no_fabrication_and_clean(self):
        posts = generate(self.data, 8, dt.date(2026, 11, 2))
        for p in posts:
            text = p["見出し"] + p["キャプション"] + p["画像構成案"]
            self.assertNotIn("円", text)  # 料金は未入力なので出さない
            self.assertEqual(checker.check_text(text), [], p["見出し"])
            self.assertTrue(p["ハッシュタグ"].count("#") <= 5)
            self.assertEqual(p["人間確認"], "未")

    def test_missing_price_is_listed_for_confirmation(self):
        posts = generate(self.data, 1, dt.date(2026, 11, 2))
        self.assertIn("料金が未入力", posts[0]["要確認事項"])

    def test_template_requires_input(self):
        self.assertTrue(validate(load_client(TEMPLATE)))
        self.assertEqual(validate(self.data), [])


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        orders.create_client(self.root, "t-salon", SAMPLE)
        self.data = orders.load_client_of(self.root, "t-salon")
        posts = generate(self.data, 4, dt.date(2026, 11, 2))
        self.od = orders.new_order(self.root, "t-salon", "trial", posts)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_deliver_blocked_until_human_approval(self):
        out, s = orders.deliver(self.od, self.data)
        self.assertIsNone(out)
        self.assertEqual(len(s["blocked"]), 4)

        posts = orders.read_posts(self.od / "posts.csv")
        for p in posts:
            p["人間確認"] = "済"
        posts[0]["キャプション"] += "\nシミが消える！"
        orders.write_posts(self.od / "posts.csv", posts)
        out, s = orders.deliver(self.od, self.data)
        self.assertIsNone(out)  # NG表現が残っている

        posts[0]["キャプション"] = posts[0]["キャプション"].replace("\nシミが消える！", "")
        orders.write_posts(self.od / "posts.csv", posts)
        out, s = orders.deliver(self.od, self.data)
        self.assertIsNotNone(out)
        for name in ["投稿一覧.csv", "納品資料.md", "canva一括作成用.csv"]:
            self.assertTrue((out / name).exists(), name)
        self.assertNotIn("確認メモ", (out / "投稿一覧.csv").read_text(encoding="utf-8-sig"))
        self.assertEqual(orders.load_status(self.od)["status"], "納品データ作成済")

    def test_status_list(self):
        with self.assertRaises(ValueError):  # 納品データなしで「顧客確認待ち」にはできない
            orders.set_status(self.od, "顧客確認待ち")
        orders.set_status(self.od, "自己確認中")
        rows = orders.list_orders(self.root)
        self.assertEqual(rows[0]["状態"], "自己確認中")
        self.assertEqual(rows[0]["確認済"], "0/4")


if __name__ == "__main__":
    unittest.main()
