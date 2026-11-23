import unittest
import cv2
import numpy as np
from image_regions import valid_region
from preprocess_image import preprocess_image, _attached_stem, _flower_component, _validate_calyx
from feature_extractor import features_from_masks
from similarity import Descriptor, GROUPS
from source_filter import signature, same_source


class RegionTests(unittest.TestCase):
    def test_calyx_rejects_background_and_accepts_attached_foreground(self):
        flower = np.zeros((100, 100), np.uint8)
        flower[20:60, 30:70] = 255
        candidate = np.zeros_like(flower)
        candidate[60:65, 42:58] = 255
        self.assertFalse(_validate_calyx(candidate, flower, np.zeros_like(flower)).any())
        self.assertTrue(_validate_calyx(candidate, flower, candidate | flower).any())
        detached = np.zeros_like(flower)
        detached[80:85, 42:58] = 255
        self.assertFalse(_validate_calyx(detached, flower, detached | flower).any())

    def test_unobservable_calyx_does_not_change_other_masks(self):
        image = np.full((256, 256, 3), 230, np.uint8)
        cv2.ellipse(image, (128, 95), (52, 55), 0, 0, 360, (100, 30, 200), -1)
        cv2.line(image, (128, 150), (128, 255), (20, 90, 30), 9)
        auto = preprocess_image(image)
        unknown = preprocess_image(image, calyx_status="unobservable")
        self.assertEqual(unknown['calyx_reason'], 'unobservable')
        self.assertFalse(unknown['calyx_mask'].any())
        for key in ('flower_mask', 'stem_mask', 'valid_mask'):
            np.testing.assert_array_equal(auto[key], unknown[key])
        d = Descriptor.from_extracted(features_from_masks(unknown, 'query'))
        self.assertTrue(np.isnan(d.values[GROUPS['calyx']]).all())

    def test_warm_white_petals_are_not_removed_as_greenery(self):
        image = np.full((256, 256, 3), 245, np.uint8)
        expected = np.zeros((256, 256), np.uint8)
        cv2.ellipse(expected, (128, 100), (60, 50), 0, 0, 360, 255, -1)
        image[expected > 0] = (170, 195, 200)
        cv2.line(image, (128, 150), (128, 250), (30, 90, 40), 7)
        p = preprocess_image(image)
        retained = cv2.countNonZero(p['flower_mask'] & expected)
        self.assertGreater(retained / cv2.countNonZero(expected), .9)

    def test_stem_above_hanging_flower_and_unattached_green(self):
        flower = np.zeros((256, 256), np.uint8)
        cv2.ellipse(flower, (128, 150), (40, 45), 0, 0, 360, 255, -1)
        plant = np.zeros_like(flower)
        plant[30:105, 125:132] = 255
        stem = _attached_stem(plant, flower, 81)
        self.assertGreater(cv2.countNonZero(stem), 400)
        self.assertFalse(stem[106:].any())
        plant[:] = 0
        plant[20:90, 10:16] = 255
        self.assertFalse(_attached_stem(plant, flower, 81).any())

    def test_stem_wider_than_old_twelve_percent_limit(self):
        flower = np.zeros((256, 256), np.uint8)
        flower[30:130, 70:170] = 255
        plant = np.zeros_like(flower)
        plant[130:230, 112:129] = 255
        self.assertGreater(cv2.countNonZero(_attached_stem(plant, flower, 100)), 1500)

    def test_thin_bridge_to_secondary_blob_is_removed(self):
        mask = np.zeros((256, 256), np.uint8)
        cv2.circle(mask, (120, 100), 45, 255, -1)
        cv2.circle(mask, (185, 180), 20, 255, -1)
        cv2.line(mask, (120, 100), (185, 180), 255, 2)
        flower = _flower_component(mask)
        self.assertEqual(flower[100, 120], 255)
        self.assertEqual(flower[180, 185], 0)

    def test_replicated_texture_excluded_and_flat_background_preserved(self):
        rng = np.random.default_rng(7)
        raw = rng.integers(0, 256, (100, 120, 3), dtype=np.uint8)
        padded = cv2.copyMakeBorder(raw, 10, 18, 14, 12, cv2.BORDER_REPLICATE)
        valid = valid_region(padded)
        self.assertFalse(valid[:10].any())
        self.assertFalse(valid[-18:].any())
        self.assertFalse(valid[:, :14].any())
        self.assertFalse(valid[:, -12:].any())
        self.assertTrue((valid[10:-18, 14:-12] == 255).all())
        flat = np.full((128, 128, 3), 180, np.uint8)
        self.assertTrue(valid_region(flat).all())

    def test_known_padding_and_absent_calyx(self):
        image = np.full((256, 256, 3), 230, np.uint8)
        cv2.ellipse(image, (128, 95), (52, 55), 0, 0, 360, (100, 30, 200), -1)
        cv2.line(image, (128, 150), (128, 255), (20, 90, 30), 9)
        padding = (0, 55, 0, 0)
        p = preprocess_image(image, calyx_status="absent", padding=padding)
        self.assertFalse(p["calyx_mask"].any())
        for name in ("flower_mask", "calyx_mask", "stem_mask"):
            self.assertFalse(p[name][-55:].any())
        d = Descriptor.from_extracted(features_from_masks(p, "synthetic"))
        self.assertTrue(np.isnan(d.values[GROUPS["calyx"][:3]]).all())
        self.assertEqual(d.values[GROUPS["calyx"][-1]], 0.)

    def test_source_filter_detects_crop_but_rejects_different_content(self):
        rng = np.random.default_rng(14)
        a = rng.integers(0, 256, (256, 256, 3), np.uint8)
        a = cv2.GaussianBlur(a, (3, 3), 0)
        b = cv2.resize(a[16:240, 16:240], (256, 256))
        unrelated = rng.integers(0, 256, (256, 256, 3), np.uint8)
        sa = signature(a)
        self.assertTrue(same_source(sa, sa))
        self.assertTrue(same_source(sa, signature(b)))
        self.assertFalse(same_source(sa, signature(unrelated)))


if __name__ == "__main__":
    unittest.main()
