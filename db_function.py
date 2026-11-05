import json
from db_connection import get_connection
from utils import print_dict


def fetch_all(sql, params=()):
    """Trả về 1 list[Dict] dict: key = tên thuộc tính, value = giá trị"""
    conn = get_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                return []
            return rows
    except Exception as e:
        print(f"[ERR] Lỗi DB: {e}")
        return []

    finally:
        conn.close()


def get_image_info(image_id):
    sql = "SELECT * FROM Images WHERE image_id = %s"
    params = (image_id,)
    return fetch_all(sql, params)


def get_color_features(image_id):
    sql = "SELECT * FROM Color_Features WHERE image_id = %s"
    params = (image_id,)
    return fetch_all(sql, params)


def get_shape_features(image_id):
    sql = "SELECT * FROM Shape_Features WHERE image_id = %s"
    params = (image_id,)
    return fetch_all(sql, params)


def get_calyx_features(image_id):
    sql = "SELECT * FROM Calyx_Features WHERE image_id = %s"
    params = (image_id,)
    return fetch_all(sql, params)


def get_stem_features(image_id):
    sql = "SELECT * FROM Stem_Features WHERE image_id = %s"
    params = (image_id,)
    return fetch_all(sql, params)


def get_image_feature_from_db(image_id):
    """Trả về 1 dict thuộc tính đã trích xuất lấy từ database"""
    feats = {}
    feats["file"] = get_image_info(image_id)
    feats["color"] = get_color_features(image_id)
    feats["shape"] = get_shape_features(image_id)
    feats["calyx"] = get_calyx_features(image_id)
    feats["stem"] = get_stem_features(image_id)
    return feats


def get_all_image_id(count):
    """Lấy danh sách các image_id từ database -> trả về 1 list[Interger]"""
    sql = "SELECT image_id FROM images LIMIT %s"
    params = (count,)
    results = fetch_all(sql, params)
    id_list = [x["image_id"] for x in results]
    return id_list


def get_all_feature_from_db(count=1500):
    image_id_list = get_all_image_id(count)
    results = []

    for image_id in image_id_list:
        feature_dict = get_image_feature_from_db(image_id)
        results.append(feature_dict)

    return results


if __name__ == "__main__":
    all_features = get_all_feature_from_db(5)

    # In 1 phần tử đầu tiên cho gọn
    for image_feature in all_features:
        print_dict(image_feature)
