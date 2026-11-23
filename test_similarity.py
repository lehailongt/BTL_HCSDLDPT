import unittest

import numpy as np

from similarity import Descriptor, FIELDS, Scale


def sample(level, bin_index=0, **updates):
    hist = np.zeros(108)
    hist[bin_index] = 1
    row = dict.fromkeys(FIELDS, level)
    row.update(updates)
    return Descriptor.from_row(dict(row, hist_hsv=hist))


class SimilarityTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = sample(1), sample(2)
        self.scale = Scale.fit([self.a, self.b])

    def test_histogram_disjoint_has_fixed_contribution(self):
        result = self.scale.compare(self.a, sample(1, bin_index=107))
        self.assertEqual(result["hist_distance"], 1)
        self.assertAlmostEqual(result["total_distance"], .2)
        self.assertAlmostEqual(result["similarity"], 1/1.2)

    def test_periodic_hue(self):
        d = self.scale.compare(sample(1, mean_h=359), sample(1, mean_h=1))
        self.assertAlmostEqual(d["distances"]["color"], (2/180) / np.sqrt(7) / 2)

    def test_partial_and_missing_organs(self):
        partial = sample(1, sepal_length_ratio=0, sepal_sharpness=0,
                         stem_thickness=0, stem_width_ratio=0)
        result = self.scale.compare(self.a, partial)
        self.assertIsNone(result["distances"]["stem"])
        self.assertAlmostEqual(result["coverage"], .8)
        self.assertAlmostEqual(result["weights"]["calyx"], .125)
        missing = sample(1, calyx_area_ratio=0, stem_thickness=0)
        result = self.scale.compare(partial, missing)
        self.assertIsNone(result["distances"]["calyx"])
        self.assertAlmostEqual(result["coverage"], .7)

    def test_missing_values_do_not_set_bounds(self):
        scale = Scale.fit([self.a, self.b, sample(1, stem_thickness=0)])
        i = FIELDS.index("stem_thickness")
        self.assertEqual(scale.counts[i], 2)
        self.assertAlmostEqual(scale.low[i], 1.01)
        self.assertAlmostEqual(scale.high[i], 1.99)
        self.assertEqual(scale.normalize(sample(10))[i], 1)

    def test_constant_and_empty_columns(self):
        no_stem = sample(1, stem_thickness=0)
        scale = Scale.fit([no_stem])
        result = scale.compare(no_stem, no_stem)
        self.assertEqual(result["similarity"], 1)
        self.assertEqual(result["weights"]["color"], 1)
        self.assertIsNone(result["distances"]["shape"])

    def test_equal_quantiles_fall_back_to_extrema(self):
        scale = Scale.fit([self.a]*200 + [self.b])
        self.assertEqual(scale.low[1], 1)
        self.assertEqual(scale.high[1], 2)

    def test_invalid_histogram_and_empty_catalog(self):
        with self.assertRaises(ValueError):
            Descriptor([0]*108, [1]*25)
        with self.assertRaises(ValueError):
            Scale.fit([])


if __name__ == "__main__":
    unittest.main()
