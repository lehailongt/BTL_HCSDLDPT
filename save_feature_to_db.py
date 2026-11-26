# ---------------------------------------------------------------------------
# 8. LƯU ĐẶC TRƯNG VÀO MYSQL
# ---------------------------------------------------------------------------
import json
import math
import os
import argparse
from pathlib import Path
from db_connection import get_connection
from feature_extractor import extract_all_feature


def _to_float(x):
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"Giá trị đặc trưng không hữu hạn: {v}")
    return v


def _insert_image(cursor, file_path, species):
    """
    Insert ảnh vào bảng Images nếu chưa có (theo file_name).
    Trả về image_id.
    """
    file_name = os.path.basename(file_path)

    sql = """
        INSERT INTO Images (file_name, file_path, flower_species)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            image_id = LAST_INSERT_ID(image_id),
            file_path = VALUES(file_path),
            flower_species = COALESCE(VALUES(flower_species), flower_species)
    """
    cursor.execute(sql, (file_name, file_path, species))
    return cursor.lastrowid


def _save_color(cursor, image_id, c):
    sql = """
        INSERT INTO Color_Features
            (image_id, hist_hsv, mean_h, mean_s, std_h, std_s,
             entropy, dominant_color_ratio, gradient_s_radius)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            hist_hsv=VALUES(hist_hsv),
            mean_h=VALUES(mean_h), mean_s=VALUES(mean_s),
            std_h=VALUES(std_h), std_s=VALUES(std_s),
            entropy=VALUES(entropy),
            dominant_color_ratio=VALUES(dominant_color_ratio),
            gradient_s_radius=VALUES(gradient_s_radius)
    """
    hist = c["hist_hsv"].tolist()
    if len(hist) != 108 or min(hist) < 0 or not math.isclose(sum(hist), 1, abs_tol=1e-6):
        raise ValueError("Histogram HSV phải có 108 ô không âm và tổng bằng 1")
    hist_json = json.dumps(hist, allow_nan=False)
    cursor.execute(
        sql,
        (
            image_id,
            hist_json,
            _to_float(c["mu_H"]),
            _to_float(c["mu_S"]),
            _to_float(c["sigma_H"]),
            _to_float(c["sigma_S"]),
            _to_float(c["entropy_H"]),
            _to_float(c["dominant_ratio"]),
            _to_float(c["gradient_S_r"]),
        ),
    )


def _save_shape(cursor, image_id, s):
    sql = """
        INSERT INTO Shape_Features
            (image_id, area, perimeter, circularity, aspect_ratio, solidity,
             hu_moment_1, hu_moment_2, hu_moment_3, hu_moment_4,
             hu_moment_5, hu_moment_6, hu_moment_7)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            area=VALUES(area), perimeter=VALUES(perimeter),
            circularity=VALUES(circularity), aspect_ratio=VALUES(aspect_ratio),
            solidity=VALUES(solidity),
            hu_moment_1=VALUES(hu_moment_1), hu_moment_2=VALUES(hu_moment_2),
            hu_moment_3=VALUES(hu_moment_3), hu_moment_4=VALUES(hu_moment_4),
            hu_moment_5=VALUES(hu_moment_5), hu_moment_6=VALUES(hu_moment_6),
            hu_moment_7=VALUES(hu_moment_7)
    """
    hu = s["hu_moments"]
    if len(hu) != 7:
        raise ValueError("Cần đủ 7 Hu Moments")
    cursor.execute(
        sql,
        (
            image_id,
            _to_float(s["area_ratio"]),
            _to_float(s["perimeter"]),
            _to_float(s["circularity"]),
            _to_float(s["aspect_ratio"]),
            _to_float(s["solidity"]),
            _to_float(hu[0]),
            _to_float(hu[1]),
            _to_float(hu[2]),
            _to_float(hu[3]),
            _to_float(hu[4]),
            _to_float(hu[5]),
            _to_float(hu[6]),
        ),
    )


def _save_calyx(cursor, image_id, cl):
    sql = """
        INSERT INTO Calyx_Features
            (image_id, sepal_length_ratio, sepal_sharpness,
             calyx_adhesion, calyx_area_ratio)
        VALUES (%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            sepal_length_ratio=VALUES(sepal_length_ratio),
            sepal_sharpness=VALUES(sepal_sharpness),
            calyx_adhesion=VALUES(calyx_adhesion),
            calyx_area_ratio=VALUES(calyx_area_ratio)
    """
    cursor.execute(
        sql,
        (
            image_id,
            _to_float(cl["sepal_length_ratio"]),
            _to_float(cl["sepal_sharpness"]),
            _to_float(cl["calyx_adhesion"]),
            _to_float(cl["calyx_area_ratio"]),
        ),
    )


def _save_stem(cursor, image_id, st):
    sql = """
        INSERT INTO Stem_Features
            (image_id, stem_thickness, stem_width_ratio)
        VALUES (%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            stem_thickness=VALUES(stem_thickness),
            stem_width_ratio=VALUES(stem_width_ratio)
    """
    cursor.execute(
        sql,
        (
            image_id,
            _to_float(st["stem_thickness"]),
            _to_float(st["stem_width_ratio"]),
        ),
    )


def _write_features(cursor, features, species=None):
    image_id = _insert_image(cursor, features["file"], species)
    cursor.execute("SELECT calyx_status, stem_status FROM Image_Review WHERE image_id=%s", (image_id,))
    review = cursor.fetchone()
    calyx = features["calyx"]
    if review and review["calyx_status"] in ("absent", "unobservable"):
        calyx = dict.fromkeys(calyx, 0.)
    _save_color(cursor, image_id, features["color"])
    _save_shape(cursor, image_id, features["shape"])
    _save_calyx(cursor, image_id, calyx)
    stem = features['stem']
    if review and review['stem_status'] in ('absent','unobservable'):
        stem = dict.fromkeys(stem,0.)
    _save_stem(cursor, image_id, stem)
    return image_id


def save_features_to_db(feature_dict, species=None):
    """
    Lưu dict đặc trưng (output của extract_feature) vào MySQL.
    Trả về image_id hoặc None nếu lỗi.
    """
    from image_review import read_reviews
    read_reviews()
    conn = get_connection()
    if not conn:
        print("[ERR] Không kết nối được DB")
        return None
    try:
        with conn.cursor() as cursor:
            image_id = _write_features(cursor, feature_dict, species)
        conn.commit()
        return image_id
    except Exception as e:
        conn.rollback()
        print(f"[ERR] Lưu DB thất bại ({feature_dict.get('file')}): {e}")
        return None
    finally:
        conn.close()


def main():
    from image_review import read_reviews
    parser = argparse.ArgumentParser(description="Trích rút và lưu bốn bộ đặc trưng")
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    args = parser.parse_args()
    paths = sorted(args.data.resolve().glob("*.jpg"),
                   key=lambda p: (not p.stem.isdecimal(), int(p.stem) if p.stem.isdecimal() else p.name))
    if not paths:
        parser.error(f"Không tìm thấy tệp JPG ở {args.data}")
    reviews = read_reviews()
    records = []
    for index, path in enumerate(paths, 1):
        records.append(extract_all_feature(path, reviews.get(path.name, "unknown")))
        if index % 100 == 0:
            print(f"Đã trích rút {index}/{len(paths)}", flush=True)

    conn = get_connection()
    if conn is None:
        raise RuntimeError("Chưa kết nối được MySQL")
    try:
        with conn.cursor() as cursor:
            for features in records:
                _write_features(cursor, features)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Đã ghi đủ bốn nhóm đặc trưng cho {len(records)} ảnh")


if __name__ == "__main__":
    main()
