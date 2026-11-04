import os
import pymysql
from dotenv import load_dotenv

# Load các biến từ file .env vào môi trường
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),  # Sửa lỗi process. -> os.getenv
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),  # Lấy từ .env
    "database": os.getenv("DB_NAME", "flower_image_db"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


def get_connection():
    """Tạo kết nối tới MySQL bằng pymysql."""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except pymysql.Error as e:
        print(f"[DB] Lỗi kết nối MySQL: {e}")
        return None


# Test nhanh (bỏ đi khi đưa vào project)
if __name__ == "__main__":
    conn = get_connection()
    if conn:
        print("✅ Kết nối thành công!")
        conn.close()
    else:
        print("❌ Kết nối thất bại, kiểm tra lại file .env và MySQL server.")
