# ---------------------------------------------------------------------------
# 8. LƯU ĐẶC TRƯNG VÀO MYSQL
# ---------------------------------------------------------------------------
import json
import math
import os
from db_connection import get_connection
from feature_extractor import extract_all_feature


def _to_float(x, default=0.0):
    """Ép về float an toàn (None/NaN -> default)."""
    try:
        print("x : ", x)
        if x is None:
            return default
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def _insert_image(cursor, file_path, species):
    """
    Insert ảnh vào bảng Images nếu chưa có (theo file_path).
    Trả về image_id.
    """
    file_name = os.path.basename(file_path)

    sql = """
        INSERT INTO Images (file_name, file_path, flower_species)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE image_id = LAST_INSERT_ID(image_id)
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
    hist_json = json.dumps(c["hist_hsv"].tolist())  # list 108 float
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


def save_features_to_db(feature_dict, species=None):
    """
    Lưu dict đặc trưng (output của extract_feature) vào MySQL.
    Trả về image_id hoặc None nếu lỗi.
    """
    conn = get_connection()
    if not conn:
        print("[ERR] Không kết nối được DB")
        return None
    try:
        with conn.cursor() as cursor:
            image_id = _insert_image(cursor, feature_dict["file"], species=species)
            print("insert OK")
            _save_color(cursor, image_id, feature_dict["color"])
            print("color OK")
            _save_shape(cursor, image_id, feature_dict["shape"])
            print("shape OK")
            _save_calyx(cursor, image_id, feature_dict["calyx"])
            print("calyx OK")
            _save_stem(cursor, image_id, feature_dict["stem"])
            print("stem OK")
        conn.commit()
        return image_id
    except Exception as e:
        conn.rollback()
        print(f"[ERR] Lưu DB thất bại ({feature_dict.get('file')}): {e}")
        return None
    finally:
        conn.close()


if __name__ == "__main__":
    path = "data/1.jpg"
    feats = extract_all_feature(path)
    print(feats)
    save_features_to_db(feats, "bong hoa")
