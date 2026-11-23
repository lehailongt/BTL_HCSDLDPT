import unittest
import numpy as np
import cv2
from preprocess_image import _edge_stem
from feature_extractor import circular_hue_stats
from similarity import Descriptor, Scale, FIELDS
from test_similarity import sample


class QualityTests(unittest.TestCase):
    def test_missing_reason_identifies_which_image_lacks_measurement(self):
        present=sample(1)
        missing=sample(1,stem_thickness=0,stem_width_ratio=0)
        scale=Scale.fit([present,missing,sample(2)])
        self.assertEqual(scale.compare(missing,present)['missing_reason']['stem'],
                         'Ảnh truy vấn chưa đo được')
        self.assertEqual(scale.compare(present,missing)['missing_reason']['stem'],
                         'Ảnh kết quả chưa đo được')
        self.assertEqual(scale.compare(missing,missing)['missing_reason']['stem'],
                         'Cả truy vấn và kết quả chưa đo được')

    def test_stem_with_dark_shadow_on_one_side(self):
        flower=np.zeros((256,256),np.uint8);flower[50:150,80:180]=255
        image=np.full((256,256,3),230,np.uint8)
        image[150:,:126]=(10,30,10)
        image[150:,126:134]=(20,140,40)
        valid=np.full((256,256),255,np.uint8)
        stem=_edge_stem(image,flower,valid,0,2,True)
        self.assertGreater(cv2.countNonZero(stem),200)
        self.assertFalse(stem[:150].any())
        self.assertFalse(stem[:,:120].any())

    def test_edge_fallback_needs_edges_and_respects_valid_pixels(self):
        flower=np.zeros((256,256),np.uint8);flower[50:150,80:180]=255
        image=np.full((256,256,3),(30,110,40),np.uint8)
        valid=np.full((256,256),255,np.uint8);valid[225:]=0
        self.assertFalse(_edge_stem(image,flower,valid).any())
        image[150:,126:133]=(20,50,30)
        stem=_edge_stem(image,flower,valid)
        self.assertGreater(cv2.countNonZero(stem),100)
        self.assertFalse(stem[225:].any())

    def test_hue_wrap_and_uniform_uncertainty(self):
        mean, std = circular_hue_stats([359,1])
        self.assertLess(min(mean,360-mean),1e-6)
        self.assertAlmostEqual(std,1,places=3)
        mean,std=circular_hue_stats([0,90,180,270])
        self.assertGreater(std,300)
        self.assertTrue(np.isnan(sample(1,mean_h=mean,std_h=std).values[0]))

    def test_confirmed_absence_differs_from_unobservable(self):
        hist=np.zeros(108);hist[0]=1
        absent=Descriptor(hist,[1.]*len(FIELDS),'absent')
        present=Descriptor(hist,[1.]*len(FIELDS),'present')
        unknown=Descriptor(hist,[1.]*len(FIELDS),'unobservable')
        scale=Scale.fit([present,absent,sample(2)])
        self.assertEqual(scale.compare(present,absent)['distances']['calyx'],1)
        self.assertEqual(scale.compare(absent,absent)['distances']['calyx'],0)
        self.assertIsNone(scale.compare(absent,unknown)['distances']['calyx'])

    def test_calibrated_distance_is_not_clipped(self):
        a,b=sample(1),sample(2)
        scale=Scale.fit([a,b]);scale.factors=dict.fromkeys(('color','shape','calyx','stem'),.1)
        self.assertGreater(scale.compare(a,b)['total_distance'],1)
        self.assertEqual(scale.compare(a,a)['similarity'],1)

    def test_hs_marginal_reduces_value_only_difference(self):
        a,b=sample(1,bin_index=0),sample(1,bin_index=2)
        scale=Scale.fit([a,b],hist_mode='hs_mix')
        self.assertAlmostEqual(scale.compare(a,b)['hist_distance'],.5)


if __name__=='__main__':
    unittest.main()
