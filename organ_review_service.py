"""Preview/save reviewed organs; restore the file when a database save reports failure."""
from datetime import datetime,timezone
from pathlib import Path
from threading import RLock
import cv2
import numpy as np
from db_connection import get_connection
from db_function import read_catalog
from feature_extractor import features_from_masks
from preprocess_image import preprocess_image
from save_feature_to_db import _save_calyx,_save_stem
from organ_annotations import image_key,read_annotation,apply_annotation,write_annotation,annotation_path

LOCK=RLock()


def preview(image,payload,states=None):
    states=states or {}
    states={g:payload['organs'].get(g,{}).get('status',states.get(g,'unknown')) for g in ('calyx','stem')}
    prep=preprocess_image(image,calyx_status=states['calyx'],stem_status=states['stem'],use_annotations=False)
    corrected=apply_annotation(prep,payload)
    return corrected,features_from_masks(corrected,'review')


def save_review(image_id,expected_key,payload,note,source='interactive_review'):
    if not note.strip() or len(note)>1000:raise ValueError('Cần ghi căn cứ kiểm tra, tối đa 1.000 ký tự.')
    with LOCK:
        rows=read_catalog();selected=next((r for r in rows if r[0]==image_id),None)
        if selected is None:raise ValueError('Không tìm thấy ảnh trong kho.')
        image=cv2.imdecode(np.frombuffer(Path(selected[2]).read_bytes(),np.uint8),1)
        if image is None:raise ValueError('Không đọc được ảnh trong kho.')
        if image_key(image)!=expected_key:raise ValueError('Ảnh đã thay đổi. Hãy mở lại và kiểm tra vùng trước khi lưu.')
        preview(image,payload,{g:getattr(selected[3],g+'_status') for g in ('calyx','stem')})
        aliases=[]
        for row in rows:
            other=cv2.imdecode(np.frombuffer(Path(row[2]).read_bytes(),np.uint8),1)
            if other is not None and image_key(other)==expected_key:aliases.append(row)
        if not any(r[0]==image_id for r in aliases):raise ValueError('Ảnh đã thay đổi trong lúc kiểm tra. Hãy mở lại ảnh.')
        data=dict(payload,note=note.strip(),updated_at=datetime.now(timezone.utc).isoformat(),
                  source=source,image_names=[r[1] for r in aliases])
        path=annotation_path(image);previous=path.read_bytes() if path.exists() else None
        conn=get_connection()
        if conn is None:raise RuntimeError('Chưa kết nối được MySQL.')
        try:
            with conn.cursor() as c:
                for row in aliases:
                    # Unreviewed organ states remain untouched; explicit unknown resets that organ.
                    c.execute('SELECT calyx_status,stem_status FROM Image_Review WHERE image_id=%s',(row[0],))
                    current=c.fetchone() or {'calyx_status':'unknown','stem_status':'unknown'}
                    states={g:data['organs'].get(g,{}).get('status',current[g+'_status']) for g in ('calyx','stem')}
                    alias_prep=apply_annotation(preprocess_image(image,calyx_status=states['calyx'],stem_status=states['stem'],use_annotations=False),data)
                    alias_features=features_from_masks(alias_prep,row[2])
                    _save_calyx(c,row[0],alias_features['calyx']);_save_stem(c,row[0],alias_features['stem'])
                    c.execute('''INSERT INTO Image_Review(image_id,calyx_status,stem_status,note)
                                 VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE
                                 calyx_status=VALUES(calyx_status),stem_status=VALUES(stem_status),note=VALUES(note)''',
                              (row[0],states['calyx'],states['stem'],note.strip()))
                write_annotation(image,data)
            conn.commit()
        except Exception:
            conn.rollback()
            if previous is None:
                if path.exists():path.unlink()
            else:path.write_bytes(previous)
            raise
        finally:conn.close()
        return [r[1] for r in aliases]
