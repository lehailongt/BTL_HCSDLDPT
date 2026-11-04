from db_connection import get_connection


def get_all_images_basic():
    """Lấy danh sách tất cả ảnh (chỉ lấy thông tin cơ bản)."""
    conn = get_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as cursor:
            sql = "SELECT image_id, file_name, file_path, flower_species FROM Images"
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        conn.close()


def get_image_full_details(image_id):
    """Lấy TOÀN BỘ thông tin của 1 ảnh (kết hợp tất cả các bảng)."""
    conn = get_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cursor:
            # Dùng LEFT JOIN để lấy dữ liệu từ tất cả các bảng
            sql = """
                SELECT
                    i.*,
                    c.hist_hsv, c.mean_h, c.mean_s, c.std_h, c.std_s,
                    c.entropy, c.dominant_color_ratio, c.gradient_s_radius,
                    s.area, s.perimeter, s.circularity, s.aspect_ratio, s.solidity,
                    s.hu_moment_1, s.hu_moment_2, s.hu_moment_3,
                    s.hu_moment_4, s.hu_moment_5, s.hu_moment_6, s.hu_moment_7,
                    cal.sepal_length_ratio, cal.sepal_sharpness,
                    cal.calyx_adhesion, cal.calyx_area_ratio,
                    st.stem_thickness, st.stem_width_ratio
                FROM Images i
                LEFT JOIN Color_Features c ON i.image_id = c.image_id
                LEFT JOIN Shape_Features s ON i.image_id = s.image_id
                LEFT JOIN Calyx_Features cal ON i.image_id = cal.image_id
                LEFT JOIN Stem_Features st ON i.image_id = st.image_id
                WHERE i.image_id = %s
            """
            cursor.execute(sql, (image_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def get_features_from_db():
    """
    Hàm quan trọng nhất: Lấy toàn bộ vector đặc trưng của tất cả ảnh
    để đưa vào thuật toán tìm kiếm tương đồng (Cosine Similarity).
    Trả về: List các dictionary, mỗi dict chứa id, path và các đặc trưng số.
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as cursor:
            # Chỉ lấy các trường số học (bỏ qua JSON histogram để tránh nặng máy)
            sql = """
                SELECT
                    i.image_id, i.file_path, i.flower_species,
                    c.mean_h, c.mean_s, c.std_h, c.std_s, c.entropy, c.dominant_color_ratio,
                    s.area, s.perimeter, s.circularity, s.aspect_ratio, s.solidity,
                    s.hu_moment_1, s.hu_moment_2, s.hu_moment_3,
                    s.hu_moment_4, s.hu_moment_5, s.hu_moment_6, s.hu_moment_7,
                    cal.sepal_length_ratio, cal.sepal_sharpness, cal.calyx_adhesion,
                    st.stem_thickness, st.stem_width_ratio
                FROM Images i
                LEFT JOIN Color_Features c ON i.image_id = c.image_id
                LEFT JOIN Shape_Features s ON i.image_id = s.image_id
                LEFT JOIN Calyx_Features cal ON i.image_id = cal.image_id
                LEFT JOIN Stem_Features st ON i.image_id = st.image_id
            """
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        conn.close()


# --- TEST THỬ ---
if __name__ == "__main__":
    print("1. Lấy danh sách ảnh cơ bản:")
    print(get_all_images_basic()[:2])  # In thử 2 ảnh đầu

    print("\n2. Lấy toàn bộ đặc trưng để tìm kiếm:")
    data = get_features_from_db()
    if data:
        print(f"Đã lấy được {len(data)} ảnh.")
        print("Các trường của ảnh đầu tiên:", list(data[0].keys()))
