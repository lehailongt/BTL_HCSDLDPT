"""Thông tin xác nhận của nhóm, lưu riêng với các đặc trưng nội dung."""
import argparse
from pathlib import Path
from db_connection import get_connection

SCHEMA = """
CREATE TABLE IF NOT EXISTS Image_Review (
    image_id INT PRIMARY KEY,
    calyx_status ENUM('unknown','present','absent','unobservable') NOT NULL DEFAULT 'unknown',
    stem_status ENUM('unknown','present','absent','unobservable') NOT NULL DEFAULT 'unknown',
    note VARCHAR(1000) NOT NULL DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES Images(image_id) ON DELETE CASCADE
)
"""


def read_organ_reviews():
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Chưa kết nối được MySQL.")
    try:
        with conn.cursor() as cursor:
            cursor.execute(SCHEMA)
            cursor.execute("SHOW COLUMNS FROM Image_Review LIKE 'calyx_status'")
            if "unobservable" not in cursor.fetchone()["Type"]:
                cursor.execute("ALTER TABLE Image_Review MODIFY calyx_status "
                               "ENUM('unknown','present','absent','unobservable') "
                               "NOT NULL DEFAULT 'unknown'")
            cursor.execute("SHOW COLUMNS FROM Image_Review LIKE 'stem_status'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE Image_Review ADD stem_status "
                               "ENUM('unknown','present','absent','unobservable') "
                               "NOT NULL DEFAULT 'unknown'")
            cursor.execute("""SELECT i.file_name, r.calyx_status, r.stem_status
                              FROM Image_Review r JOIN Images i USING(image_id)""")
            return {row["file_name"]: {g:row[g+'_status'] for g in ('calyx','stem')} for row in cursor.fetchall()}
    finally:
        conn.close()


def read_reviews():
    return {name:review['calyx'] for name,review in read_organ_reviews().items()}


def main():
    from feature_extractor import extract_all_feature
    from save_feature_to_db import _save_calyx, _save_stem

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Tên tệp trong bảng Images")
    parser.add_argument("--calyx", choices=("unknown", "present", "absent", "unobservable"))
    parser.add_argument("--stem", choices=("unknown", "present", "absent", "unobservable"))
    parser.add_argument("--note", required=True, help="Căn cứ xác nhận của nhóm")
    args = parser.parse_args()
    if args.calyx is None and args.stem is None:
        parser.error("Cần ít nhất --calyx hoặc --stem.")
    if not args.note.strip() or len(args.note) > 1000:
        parser.error("Ghi căn cứ xác nhận từ 1 đến 1.000 ký tự.")
    reviews = read_organ_reviews()
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Chưa kết nối được MySQL.")
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT image_id, file_path FROM Images WHERE file_name=%s",
                           (args.file,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Không tìm thấy ảnh trong kho.")
            path = Path(row["file_path"])
            if not path.is_absolute():
                path = Path(__file__).resolve().parent / path
            # Keep an existing reviewed polygon bundle in sync with CLI state edits.
            import cv2
            import numpy as np
            from organ_annotations import read_annotation,image_key
            image=cv2.imdecode(np.frombuffer(path.read_bytes(),np.uint8),1)
            annotation=read_annotation(image) if image is not None else None
            if annotation is not None:
                from organ_review_service import save_review
                payload=dict(annotation,organs=dict(annotation['organs']))
                for organ,state in (('calyx',args.calyx),('stem',args.stem)):
                    if state is None:continue
                    old=payload['organs'].get(organ,{})
                    payload['organs'][organ]=old if state=='present' and old.get('status')=='present' else {'status':state,'kind':'state','polygons':[]}
                names=save_review(row['image_id'],image_key(image),payload,args.note,source='cli_review')
                print('Đã đồng bộ xác nhận và vùng hiệu chỉnh: '+', '.join(names))
                return
            previous = reviews.get(args.file, {})
            calyx_status = args.calyx or previous.get('calyx','unknown')
            stem_status = args.stem or previous.get('stem','unknown')
            features = extract_all_feature(path, calyx_status=calyx_status,stem_status=stem_status)
            cursor.execute("""INSERT INTO Image_Review(image_id, calyx_status, stem_status, note)
                              VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE
                              calyx_status=VALUES(calyx_status), stem_status=VALUES(stem_status), note=VALUES(note)""",
                           (row["image_id"], calyx_status, stem_status, args.note.strip()))
            if args.calyx is not None:
                _save_calyx(cursor, row["image_id"], features["calyx"])
            if args.stem is not None:
                _save_stem(cursor, row["image_id"], features["stem"])
        conn.commit()
        print(f"Đã lưu xác nhận và cập nhật đặc trưng cho {args.file}.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
