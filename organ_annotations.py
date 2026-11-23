"""Reviewed organ polygons, bound to decoded pixels rather than a filename."""
import hashlib
import json
import os
from pathlib import Path
import uuid
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parent/'annotations'/'organs'
STATES=('unknown','present','absent','unobservable')


def image_key(image):
    a=np.ascontiguousarray(image,dtype=np.uint8)
    return hashlib.sha256(str(a.shape).encode('ascii')+a.tobytes()).hexdigest()


def annotation_path(image):
    return ROOT/(image_key(image)+'.json')


def read_annotation(image):
    path=annotation_path(image)
    if not path.exists():return None
    data=json.loads(path.read_text(encoding='utf8'))
    validate(data,image)
    return data


def validate(data,image):
    if data.get('version')!=1 or data.get('image_key')!=image_key(image):
        raise ValueError('Vùng hiệu chỉnh không khớp nội dung ảnh hiện tại.')
    if not isinstance(data.get('organs'),dict) or set(data['organs'])-{'calyx','stem'}:
        raise ValueError('Bộ phận hiệu chỉnh không hợp lệ.')
    h,w=image.shape[:2]
    for organ,entry in data['organs'].items():
        if entry.get('status') not in STATES:raise ValueError('Trạng thái hiệu chỉnh không hợp lệ.')
        polygons=entry.get('polygons',[])
        if not isinstance(polygons,list) or len(polygons)>30:raise ValueError('Quá nhiều vùng hiệu chỉnh.')
        if entry.get('kind','polygon') not in ('polygon','state'):
            raise ValueError('Kiểu hiệu chỉnh không hợp lệ.')
        if entry['status']=='present' and not polygons and entry.get('kind')!='state':
            raise ValueError('Cần khoanh vùng cho bộ phận đã chọn Có; hoặc chọn Giữ tự động.')
        for polygon in polygons:
            points=np.asarray(polygon,dtype=float)
            if points.ndim!=2 or points.shape[1]!=2 or not 3<=len(points)<=300 or not np.isfinite(points).all():
                raise ValueError('Mỗi vùng cần từ 3 đến 300 điểm hợp lệ.')
            if ((points[:,0]<0)|(points[:,0]>=w)|(points[:,1]<0)|(points[:,1]>=h)).any():
                raise ValueError('Điểm khoanh vùng nằm ngoài ảnh.')
            if abs(cv2.contourArea(points.astype(np.float32)))<3:
                raise ValueError('Vùng khoanh quá nhỏ hoặc các điểm thẳng hàng.')
    return data


def write_annotation(image,data):
    validate(data,image)
    ROOT.mkdir(parents=True,exist_ok=True)
    path=annotation_path(image);staging=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    try:
        staging.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
        os.replace(staging,path)
    finally:
        if staging.exists():staging.unlink()


def oriented_measurement(mask,flower):
    ys,xs=np.where(mask>0)
    if len(xs)<5:return None
    box=cv2.boxPoints(cv2.minAreaRect(np.column_stack((xs,ys)).astype(np.float32)))
    edges=np.roll(box,-1,axis=0)-box
    direction=edges[np.linalg.norm(edges,axis=1).argmax()]
    angle=float(np.degrees(np.arctan2(direction[1],direction[0]))-90)
    h,w=mask.shape;side=int(np.ceil(np.hypot(h,w)))
    transform=cv2.getRotationMatrix2D((w/2,h/2),angle,1)
    transform[:,2]+=[(side-w)/2,(side-h)/2]
    def warp(a):return cv2.warpAffine(a,transform,(side,side),flags=cv2.INTER_NEAREST)
    return {'mask':mask,'measurement_mask':warp(mask),'flower_mask':warp(flower),
            'angle':angle,'score':None,'source':'reviewed_polygon'}


def apply_annotation(prep,data,overrides=None):
    if data is None:return prep
    validate(data,prep['bgr']);overrides=overrides or {}
    result=dict(prep);provenance=dict(prep.get('organ_provenance',{}))
    for organ,entry in data['organs'].items():
        state=entry['status'];explicit=overrides.get(organ,'unknown')
        if state=='unknown' or (explicit!='unknown' and explicit!=state):continue
        mask=np.zeros_like(prep['flower_mask'])
        if state=='present':
            if entry.get('kind')=='state':mask=prep[organ+'_mask'].copy()
            else:
                for polygon in entry['polygons']:
                    cv2.fillPoly(mask,[np.rint(polygon).astype(np.int32)],255)
                mask &= prep['valid_mask']
                mask[prep['flower_mask']>0]=0
                if cv2.countNonZero(mask)<5:
                    raise ValueError('Vùng hiệu chỉnh không còn đủ pixel sau khi loại bông và biên lặp.')
        result[organ+'_mask']=mask
        result[organ+'_status']=state
        provenance[organ]='reviewed_polygon' if state=='present' and entry.get('kind')!='state' else 'reviewed_state'
        if organ=='stem' and entry.get('kind')!='state':result['stem_measurement']=oriented_measurement(mask,prep['flower_mask'])
        elif organ=='stem' and state in ('absent','unobservable'):result['stem_measurement']=None
        else:
            if organ=='calyx':
                result['calyx_reason']=('reviewed' if mask.any() else 'unresolved') if state=='present' else state
                if entry.get('kind')!='state':result['calyx_attachment']=state=='present'
    if np.any((result['stem_mask']>0)&(result['calyx_mask']>0)):
        # The reviewed organ takes precedence over an automatic estimate.
        if provenance.get('stem')=='reviewed_polygon' and provenance.get('calyx')=='reviewed_polygon':
            raise ValueError('Vùng đài và cuống đang chồng nhau. Cần chỉnh lại trước khi lưu.')
        if provenance.get('stem')=='reviewed_polygon':
            result['calyx_mask']=result['calyx_mask'].copy();result['calyx_mask'][result['stem_mask']>0]=0
        elif provenance.get('calyx')=='reviewed_polygon':
            result['stem_mask']=result['stem_mask'].copy();result['stem_mask'][result['calyx_mask']>0]=0
            result['stem_measurement']=oriented_measurement(result['stem_mask'],prep['flower_mask'])
    result['organ_provenance']=provenance
    return result
