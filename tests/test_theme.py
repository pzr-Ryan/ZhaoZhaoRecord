import unittest

from ledger import theme


class ThemeTests(unittest.TestCase):
    def test_six_presets(self):
        self.assertEqual(len(theme.PRESETS), 6)
        self.assertEqual(theme.PRESETS[0].name, "蓝白")
        self.assertEqual(theme.PRESETS[0].accent, "#2563EB")
        self.assertEqual(theme.PRESETS[0].bg, "#F5F7FB")
        self.assertEqual(theme.PRESETS[0].surface, "#FFFFFF")

    def test_text_on_accent_contrast(self):
        for palette in theme.PRESETS:
            ratio = theme.contrast_ratio(palette.accent, palette.text_on_accent)
            self.assertGreaterEqual(ratio, 4.0, palette.name)

    def test_custom_palette(self):
        palette = theme.build_palette("自定义", "#0ea5e9")
        self.assertEqual(palette.accent, "#0EA5E9")
        self.assertNotEqual(palette.accent_soft, palette.accent)
        self.assertEqual(theme.contrast_ratio("#000000", "#FFFFFF"), 21.0)

    def test_mix_and_lighten(self):
        self.assertEqual(theme.mix("#000000", "#FFFFFF", 0.5), "#808080")
        self.assertEqual(theme.lighten("#000000", 1.0), "#FFFFFF")

    def test_resolve_defaults(self):
        class FakeStore:
            def __init__(self):
                self.data = {}

            def get_setting(self, key, default=None):
                return self.data.get(key, default)

        store = FakeStore()
        self.assertEqual(theme.resolve(store).name, "蓝白")
        store.data["theme.preset"] = "青碧"
        self.assertEqual(theme.resolve(store).name, "青碧")
        store.data["theme.preset"] = "自定义"
        store.data["theme.accent"] = "#123456"
        self.assertEqual(theme.resolve(store).accent, "#123456")


if __name__ == "__main__":
    unittest.main()
