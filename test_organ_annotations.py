import json
from pathlib import Path
import shutil
import uuid
import unittest
from unittest.mock import patch
import cv2
import numpy as np
import organ_annotations as annotations
import organ_review_service as service
from preprocess_image import preprocess_image
from feature_extractor import features_from_masks,extract_stem_features
from similarity import Descriptor


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.root=Path.cwd()/('_annotation_test_'+uuid.uuid4().hex)
        self.root.mkdir()
        self.assertEqual(self.root.resolve().parent,Path.cwd().resolve())
        self.root_patch=patch.object(annotations,'ROOT',self.root/'annotations');self.root_patch.start()
        self.image=np.random.default_rng(12).integers(225,245,(160,160,3),dtype=np.uint8)
        cv2.circle(self.image,(80,55),30,(120,30,220),-1)
        cv2.line(self.image,(80,85),(80,159),(20,80,30),7)
        self.payload={'version':1,'image_key':annotations.image_key(self.image),
                      'organs':{'stem':{'status':'present','polygons':[[[77,92],[83,92],[83,150],[77,150]]]}}}

    def tearDown(self):
        self.root_patch.stop()
        self.assertEqual(self.root.resolve().parent,Path.cwd().resolve())
        shutil.rmtree(self.root)

    def test_exact_content_reuse_and_other_features_unchanged(self):
        before=preprocess_image(self.image,use_annotations=False)
        annotations.write_annotation(self.image,self.payload)
        after=preprocess_image(self.image)
        for key in ('flower_mask','hsv','valid_mask'):
            np.testing.assert_array_equal(before[key],after[key])
        self.assertEqual(after['stem_status'],'present')
        self.assertEqual(after['organ_provenance']['stem'],'reviewed_polygon')
        self.assertEqual(cv2.countNonZero(after['stem_mask']),7*59)
        changed=self.image.copy();changed[0,0]=0
        self.assertIsNone(annotations.read_annotation(changed))
        with self.assertRaises(ValueError):annotations.apply_annotation(preprocess_image(changed,use_annotations=False),self.payload)

    def test_out_of_bounds_and_overlap_rejected(self):
        bad=json.loads(json.dumps(self.payload));bad['organs']['stem']['polygons'][0][0][0]=-1
        with self.assertRaises(ValueError):annotations.validate(bad,self.image)
        bad=json.loads(json.dumps(self.payload));bad['organs']['calyx']=bad['organs']['stem']
        with self.assertRaises(ValueError):service.preview(self.image,bad)

    def test_reviewed_horizontal_stem_is_not_measured_as_wide_blob(self):
        mask=np.zeros((160,160),np.uint8);mask[80:87,70:150]=255
        flower=np.zeros_like(mask);cv2.circle(flower,(45,83),25,255,-1)
        prep={'stem_mask':mask,'flower_mask':flower,'stem_measurement':annotations.oriented_measurement(mask,flower)}
        measured=extract_stem_features(prep)
        self.assertGreaterEqual(measured['stem_thickness'],5)
        self.assertLessEqual(measured['stem_thickness'],9)

    def test_state_only_confirmation_preserves_automatic_mask(self):
        data={'version':1,'image_key':annotations.image_key(self.image),
              'organs':{'stem':{'status':'present','kind':'state','polygons':[]}}}
        before=preprocess_image(self.image,use_annotations=False)
        after=annotations.apply_annotation(before,data)
        np.testing.assert_array_equal(before['stem_mask'],after['stem_mask'])
        self.assertEqual(after['stem_status'],'present')

    def test_explicit_query_state_overrides_saved_mask(self):
        annotations.write_annotation(self.image,self.payload)
        result=preprocess_image(self.image,stem_status='unobservable')
        self.assertFalse(result['stem_mask'].any())
        self.assertEqual(result['stem_status'],'unobservable')

    def test_absence_and_reset_to_automatic(self):
        absent=json.loads(json.dumps(self.payload));absent['organs']['stem']={'status':'absent','polygons':[]}
        annotations.write_annotation(self.image,absent)
        self.assertFalse(preprocess_image(self.image)['stem_mask'].any())
        absent['organs']['stem']['status']='unknown'
        annotations.write_annotation(self.image,absent)
        actual=preprocess_image(self.image);expected=preprocess_image(self.image,use_annotations=False)
        np.testing.assert_array_equal(actual['stem_mask'],expected['stem_mask'])

    def fake_catalog(self):
        path=self.root/'one.png';cv2.imencode('.png',self.image)[1].tofile(str(path))
        descriptor=Descriptor.from_extracted(features_from_masks(preprocess_image(self.image,use_annotations=False),str(path)))
        return [(1,'one.png',str(path),descriptor),(2,'same_pixels.png',str(path),descriptor)]

    def test_save_updates_duplicates_and_only_organ_tables(self):
        conn=FakeConnection()
        with patch.object(service,'read_catalog',return_value=self.fake_catalog()),patch.object(service,'get_connection',return_value=conn):
            names=service.save_review(1,annotations.image_key(self.image),self.payload,'Reviewed synthetic stem')
        self.assertEqual(names,['one.png','same_pixels.png']);self.assertTrue(conn.committed)
        self.assertIsNotNone(annotations.read_annotation(self.image))
        sql=' '.join(query for query,args in conn.queries)
        self.assertNotIn('Color_Features',sql);self.assertNotIn('Shape_Features',sql)
        self.assertIn('Stem_Features',sql);self.assertIn('Calyx_Features',sql)

    def test_failed_commit_restores_annotation(self):
        old=dict(self.payload,note='previous');annotations.write_annotation(self.image,old)
        original=annotations.annotation_path(self.image).read_bytes()
        conn=FakeConnection(fail=True)
        with patch.object(service,'read_catalog',return_value=self.fake_catalog()),patch.object(service,'get_connection',return_value=conn):
            with self.assertRaises(RuntimeError):service.save_review(1,annotations.image_key(self.image),self.payload,'New review')
        self.assertTrue(conn.rolled_back)
        self.assertEqual(annotations.annotation_path(self.image).read_bytes(),original)


class FakeConnection:
    def __init__(self,fail=False):self.queries=[];self.fail=fail;self.committed=False;self.rolled_back=False
    def cursor(self):return self
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,query,args=()):self.queries.append((query,args))
    def fetchone(self):return {'calyx_status':'unknown','stem_status':'unknown'}
    def commit(self):
        if self.fail:raise RuntimeError('simulated commit failure')
        self.committed=True
    def rollback(self):self.rolled_back=True
    def close(self):pass


if __name__=='__main__':unittest.main()
