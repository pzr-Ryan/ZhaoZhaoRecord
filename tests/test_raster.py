import struct
import tkinter as tk
import unittest

from ledger import raster


class RasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:  # headless CI
            raise unittest.SkipTest("Tk display unavailable: %s" % exc)
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        raster.clear_cache()
        cls.root.destroy()

    def tearDown(self):
        raster.clear_cache()

    def test_png_header_and_size(self):
        data = raster._png(3, 2, bytes(3 * 2 * 4))
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (3, 2))
        self.assertTrue(data[-12:].startswith(b"\x00\x00\x00\x00IEND"))

    def test_round_rect_colors_and_cache(self):
        image = raster.round_rect(self.root, 40, 30, 8, "#FFFFFF",
                                  "#E7EAF0", "#F5F7FB")
        self.assertEqual((image.width(), image.height()), (40, 30))
        self.assertEqual(image.get(0, 0), (245, 247, 251))
        self.assertEqual(image.get(20, 15), (255, 255, 255))
        again = raster.round_rect(self.root, 40, 30, 8, "#FFFFFF",
                                   "#E7EAF0", "#F5F7FB")
        self.assertIs(image, again)
        self.assertEqual(raster.cache_size(), 1)

    def test_circle_has_transparent_corners(self):
        image = raster.circle(self.root, 24, "#2563EB", None)
        self.assertTrue(image.transparency_get(0, 0))
        self.assertFalse(image.transparency_get(12, 12))
        self.assertEqual(image.get(12, 12), (37, 99, 235))

    def test_ring_has_transparent_centre(self):
        image = raster.ring(self.root, 24, 3, "#2563EB", None)
        self.assertTrue(image.transparency_get(12, 12))
        self.assertFalse(image.transparency_get(12, 2))

    def test_donut_ring_is_opaque_centre_is_clear(self):
        image = raster.donut(self.root, 40, 8, [(0, 360, "#2563EB")])
        self.assertTrue(image.transparency_get(20, 20))
        self.assertFalse(image.transparency_get(20, 3))

    def test_bar_rounded_top_and_gradient(self):
        image = raster.bar_rgba(self.root, 12, 30, 4, "#2563EB", "#93B4F5")
        self.assertTrue(image.transparency_get(0, 0))
        self.assertFalse(image.transparency_get(6, 20))
        top = image.get(6, 2)
        bottom = image.get(6, 29)
        self.assertLess(top[0], bottom[0])
        self.assertNotEqual(top, bottom)


if __name__ == "__main__":
    unittest.main()
