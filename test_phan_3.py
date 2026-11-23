"""Kiểm chứng các phép đo của Câu 2 bằng pixel có tọa độ biết trước."""
import unittest

import cv2
import numpy as np

from feature_extractor import (_hist_hsv_12x3x3, extract_calyx_features,
                               extract_shape_features, extract_stem_features)


class PhepDoDacTrung(unittest.TestCase):
    def setUp(self):
        self.flower = np.zeros((80, 80), np.uint8)
        self.flower[5:25, 20:60] = 255

    def test_histogram_hai_o_bien(self):
        hsv = np.array([[[0, 0, 0], [179, 255, 255]]], np.uint8)
        hist = _hist_hsv_12x3x3(hsv, np.full((1, 2), 255, np.uint8))
        self.assertEqual(len(hist), 108)
        self.assertEqual((hist[0], hist[-1], hist.sum()), (.5, .5, 1.))

    def test_dien_tich_chu_vi_va_cuong(self):
        stem = np.zeros_like(self.flower)
        stem[35:75, 39:43] = 255
        masks = dict(flower_mask=self.flower, stem_mask=stem)
        s = extract_shape_features(masks)
        self.assertEqual((s["area_ratio"], s["perimeter"], s["solidity"]), (.125, 116., 1.))
        self.assertEqual(len(s["hu_moments"]), 7)
        self.assertEqual(extract_stem_features(masks), dict(stem_thickness=4., stem_width_ratio=.1))

    def test_goc_dinh_va_khoang_cach_dai_canh(self):
        def measure(shift):
            calyx = np.zeros_like(self.flower)
            vertices = np.array([[39, 26], [34, 36], [44, 36]]) + [0, shift]
            cv2.fillConvexPoly(calyx, vertices.astype(np.int32), 255)
            return extract_calyx_features(dict(flower_mask=self.flower, calyx_mask=calyx))

        near, far = measure(0), measure(8)
        self.assertAlmostEqual(near["sepal_length_ratio"], .25)
        self.assertAlmostEqual(near["sepal_sharpness"], 53.130102, places=5)
        self.assertAlmostEqual(far["calyx_adhesion"] - near["calyx_adhesion"], 8/40, places=6)


if __name__ == "__main__":
    unittest.main()
