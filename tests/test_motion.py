import unittest

from ledger.motion import (TRANSITION_FADE_END, TRANSITION_IN_MS, TRANSITION_MS,
                           TRANSITION_OUT_MS, TRANSITION_REVEAL,
                           TRANSITION_REVEAL_MS, TRANSITION_REVEAL_TIME,
                           page_transition)


class PageTransitionTests(unittest.TestCase):
    def test_duration_and_reveal_match_request(self):
        self.assertEqual(TRANSITION_OUT_MS, 1000)
        self.assertEqual(TRANSITION_REVEAL_MS, 750)
        self.assertEqual(TRANSITION_IN_MS, 1400)
        self.assertEqual(TRANSITION_MS, 2150)
        self.assertAlmostEqual(TRANSITION_REVEAL, 0.75)
        self.assertAlmostEqual(TRANSITION_REVEAL_TIME, 750 / 2150.0)
        self.assertAlmostEqual(TRANSITION_FADE_END, 1000 / 2150.0)

    def test_old_page_starts_fully_opaque(self):
        opacity, offset, reveal = page_transition(0.0)
        self.assertEqual(opacity, 1.0)
        self.assertEqual(offset, 1.0)
        self.assertFalse(reveal)

    def test_old_page_fades_linearly(self):
        opacity, _, _ = page_transition(TRANSITION_FADE_END * 0.1)
        self.assertAlmostEqual(opacity, 0.9, places=6)
        opacity, _, _ = page_transition(TRANSITION_FADE_END * 0.5)
        self.assertAlmostEqual(opacity, 0.5, places=6)
        opacity, _, _ = page_transition(TRANSITION_REVEAL_TIME)
        self.assertAlmostEqual(opacity, 0.25, places=6)
        opacity, _, _ = page_transition(TRANSITION_FADE_END)
        self.assertAlmostEqual(opacity, 0.0, places=6)

    def test_incoming_waits_until_75_percent_fade(self):
        opacity, offset, reveal = page_transition(TRANSITION_REVEAL_TIME - 0.001)
        self.assertGreater(opacity, 0.25)
        self.assertEqual(offset, 1.0)
        self.assertFalse(reveal)

        opacity, offset, reveal = page_transition(TRANSITION_REVEAL_TIME)
        self.assertAlmostEqual(opacity, 0.25, places=6)
        self.assertEqual(offset, 1.0)
        self.assertTrue(reveal)

    def test_incoming_slides_in_while_old_page_finishes_fade(self):
        midpoint = (TRANSITION_REVEAL_TIME + TRANSITION_FADE_END) / 2.0
        opacity, offset, reveal = page_transition(midpoint)
        self.assertGreater(opacity, 0.0)
        self.assertLess(opacity, 0.25)
        self.assertGreater(offset, 0.0)
        self.assertLess(offset, 1.0)
        self.assertTrue(reveal)

        opacity, offset, reveal = page_transition(1.0)
        self.assertEqual(opacity, 0.0)
        self.assertEqual(offset, 0.0)
        self.assertTrue(reveal)


if __name__ == "__main__":
    unittest.main()
