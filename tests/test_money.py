import unittest

from ledger import money


class ParseAmountTests(unittest.TestCase):
    def test_accepts_integer_and_decimal(self):
        self.assertEqual(money.parse_amount("25"), 2500)
        self.assertEqual(money.parse_amount("25.5"), 2550)
        self.assertEqual(money.parse_amount("0.01"), 1)
        self.assertEqual(money.parse_amount(" 1,234.56 "), 123456)
        self.assertEqual(money.parse_amount("¥12.30"), 1230)

    def test_accepts_max(self):
        self.assertEqual(money.parse_amount("9999999.99"), 999999999)

    def test_rejects_bad_values(self):
        for value in ["", " ", "abc", "-1", "0", "0.00", "1.234", "1.2.3",
                      "10000000", "1e5", "NaN", None, "12-3"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    money.parse_amount(value)


class FormatTests(unittest.TestCase):
    def test_format_cents(self):
        self.assertEqual(money.format_cents(0), "¥0.00")
        self.assertEqual(money.format_cents(5), "¥0.05")
        self.assertEqual(money.format_cents(123456), "¥1,234.56")
        self.assertEqual(money.format_cents(999999999), "¥9,999,999.99")

    def test_plain(self):
        self.assertEqual(money.format_plain(123456), "1234.56")
        self.assertEqual(money.format_plain(5), "0.05")

    def test_signed(self):
        self.assertEqual(money.format_signed(2550, "expense"), "-¥25.50")
        self.assertEqual(money.format_signed(2550, "income"), "+¥25.50")

    def test_compact(self):
        self.assertEqual(money.format_compact(0), "¥0.00")
        self.assertEqual(money.format_compact(2500), "¥25")
        self.assertIn("万", money.format_compact(12_000_000))


if __name__ == "__main__":
    unittest.main()
