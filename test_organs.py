import unittest
import cv2
import numpy as np
from organ_regions import multi_direction_stem, attachment_calyx, supported_stem, shaft_quality
from preprocess_image import preprocess_image, _edge_stem
from feature_extractor import features_from_masks, extract_stem_features
from similarity import Descriptor, GROUPS, Scale
from test_similarity import sample


class OrganTests(unittest.TestCase):
    def test_color_edges_with_equal_grayscale(self):
        # Research-only implementation; it is deliberately not deployed.
        import importlib.util
        from pathlib import Path
        path=Path('bao_cao/phan_4/danh_gia/do_on_dinh_cuong_23/experimental_preprocess_image.py')
        spec=importlib.util.spec_from_file_location('experimental_preprocess',path)
        experimental=importlib.util.module_from_spec(spec);spec.loader.exec_module(experimental)
        flower=np.zeros((160,160),np.uint8);flower[20:80,45:115]=255
        image=np.full((160,160,3),(70,100,70),np.uint8)
        image[80:,77:84]=(0,150,0)
        valid=np.full_like(flower,255)
        self.assertFalse(_edge_stem(image,flower,valid).any())
        measured=experimental._edge_stem(image,flower,valid,0,2,True,80,True)
        self.assertGreater(cv2.countNonZero(measured),300)
        self.assertFalse(measured[:80].any())

    def test_uniform_shaft_scores_above_tapering_leaf(self):
        shaft=np.zeros((100,100),np.uint8);shaft[10:90,47:54]=255
        leaf=np.zeros_like(shaft)
        cv2.fillPoly(leaf,[np.array([[50,10],[65,90],[35,90]])],255)
        self.assertGreater(shaft_quality(shaft),shaft_quality(leaf))

    def scene(self, angle=0, color=(30,80,40)):
        flower=np.zeros((160,160),np.uint8)
        cv2.circle(flower,(80,80),25,255,-1)
        stem=np.zeros_like(flower)
        direction=np.array([np.sin(np.deg2rad(angle)),np.cos(np.deg2rad(angle))])
        start=tuple(np.rint([80,80]+direction*23).astype(int))
        end=tuple(np.rint([80,80]+direction*70).astype(int))
        cv2.line(stem,start,end,255,5)
        image=np.full((160,160,3),230,np.uint8)
        image[stem>0]=color;image[flower>0]=(100,20,200)
        return image,flower,stem,np.full_like(flower,255)

    def test_eight_directions_and_brown_stalks(self):
        for angle in range(0,360,45):
            with self.subTest(angle=angle):
                image,flower,stem,valid=self.scene(angle,(35,55,90))
                result=multi_direction_stem(image,flower,flower|stem,valid)
                self.assertIsNotNone(result)
                measured=result['mask']>0
                self.assertGreater(np.mean(stem[measured]>0),.9)
                self.assertFalse((measured & (flower>0)).any())

    def test_detached_background_is_rejected(self):
        image,flower,stem,valid=self.scene()
        stray=np.zeros_like(stem);stray[15:145,10:15]=255
        image[stem>0]=230;image[stray>0]=(30,80,40)
        self.assertIsNone(multi_direction_stem(image,flower,flower|stray,valid))
        self.assertFalse(supported_stem(stray,flower,flower))

    def test_valid_border_is_respected(self):
        image,flower,stem,valid=self.scene()
        valid[135:]=0
        r=multi_direction_stem(image,flower,flower|stem,valid)
        self.assertIsNotNone(r)
        self.assertFalse(r['mask'][135:].any())

    def test_calyx_above_hanging_bloom(self):
        flower=np.zeros((160,160),np.uint8);cv2.circle(flower,(80,95),30,255,-1)
        calyx=np.zeros_like(flower);cv2.ellipse(calyx,(80,65),(16,10),0,0,360,255,-1)
        calyx[flower>0]=0
        stem=np.zeros_like(flower);stem[15:58,77:84]=255
        mask=attachment_calyx(flower,stem,calyx,flower|calyx|stem,np.full_like(flower,255))
        self.assertGreater(cv2.countNonZero(mask),50)
        self.assertFalse(mask[96:].any())

    def test_confirmed_absence_is_distinct_from_detection_failure(self):
        image,_,_,_=self.scene()
        auto=preprocess_image(image)
        absent=preprocess_image(image,stem_status='absent')
        self.assertFalse(absent['stem_mask'].any())
        for key in ('flower_mask','calyx_mask','valid_mask'):
            np.testing.assert_array_equal(auto[key],absent[key])
        descriptor=Descriptor.from_extracted(features_from_masks(absent,'synthetic'))
        self.assertTrue(np.isnan(descriptor.values[GROUPS['stem']]).all())
        self.assertEqual(descriptor.organ_state('stem'),'Không có (đã xác nhận)')
        unknown=sample(1,stem_thickness=0,stem_width_ratio=0)
        self.assertEqual(unknown.organ_state('stem'),'Chưa xác định')

    def test_confirmed_stem_states_are_compared_not_missing_measurements(self):
        present=sample(1);present.stem_status='present'
        absent=sample(1,stem_thickness=0,stem_width_ratio=0);absent.stem_status='absent'
        unknown=sample(1,stem_thickness=0,stem_width_ratio=0)
        scale=Scale.fit([present,absent,unknown,sample(2)])
        self.assertEqual(scale.compare(present,absent)['distances']['stem'],1)
        self.assertEqual(scale.compare(absent,absent)['distances']['stem'],0)
        self.assertIsNone(scale.compare(absent,unknown)['distances']['stem'])
        self.assertTrue(scale.compare(present,absent)['organ_state_comparisons']['stem'])


if __name__=='__main__':unittest.main()
