import unittest

import cv2
import numpy as np

from searcher import FlowerCatalog, decode_query
from similarity import Descriptor, FIELDS


def descriptor(level, with_stem=True):
    hist = np.zeros(108)
    hist[0] = 1
    row = dict.fromkeys(FIELDS, level)
    if not with_stem:
        row.update(stem_thickness=0, stem_width_ratio=0)
    return Descriptor.from_row(dict(row, hist_hsv=hist))


class SearchTests(unittest.TestCase):
    def test_top_k_excludes_before_sort_and_breaks_exact_ties(self):
        q, other = descriptor(1), descriptor(2)
        items = [(9, q), (3, descriptor(1, False)), (7, q), (11, other)]
        catalog = FlowerCatalog((i, str(i), str(i), d) for i, d in items)
        hits, compared = catalog.rank(q)
        self.assertEqual([h["image_id"] for h in hits], [7, 9, 3, 11])
        self.assertEqual(compared, 4)
        self.assertEqual(hits[0]["similarity"], hits[2]["similarity"])
        self.assertIsNone(hits[2]["distances"]["stem"])
        hits, compared = catalog.rank(q, top_k=2, exclude_id=7)
        self.assertEqual(([h["image_id"] for h in hits], compared), ([9, 3], 3))

    def test_sort_before_rounding(self):
        q = descriptor(1.5)
        first = descriptor(1.500001)
        second = descriptor(1.500002)
        catalog = FlowerCatalog([(1, "b", "b", second), (2, "a", "a", first),
                                 (3, "low", "low", descriptor(1)), (4, "high", "high", descriptor(2))])
        hits, _ = catalog.rank(q, top_k=2)
        self.assertEqual([h["image_id"] for h in hits], [2, 1])
        self.assertEqual(round(hits[0]["similarity"], 4), round(hits[1]["similarity"], 4))

    def test_query_size_and_padding(self):
        raw = np.zeros((64, 128, 3), np.uint8)
        raw[:32, :] = (10, 120, 220)
        data = cv2.imencode(".jpg", raw)[1].tobytes()
        image, size = decode_query(data)
        self.assertEqual(size, (128, 64))
        self.assertEqual(image.shape, (256, 256, 3))
        np.testing.assert_array_equal(image[0], image[64])
        np.testing.assert_array_equal(image[-1], image[-65])

    def test_empty_gallery_and_unreadable_upload(self):
        with self.assertRaises(ValueError):
            FlowerCatalog([])
        for payload in (b"", b"broken jpeg"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                decode_query(payload)


if __name__ == "__main__":
    unittest.main()
