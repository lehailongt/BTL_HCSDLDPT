from pprint import pprint
import cv2
import numpy as np


def read_image(file_path):
    """Đọc ảnh từ đường dẫn và chuyển đổi từ (OpenCV) sang RGB."""

    # np.fromfile giúp đọc được cả các file có tên tiếng Việt trên Windows
    img_array = np.fromfile(file_path, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError(f"Không thể đọc ảnh tại đường dẫn: {file_path}")

    # Chuyển từ BGR (mặc định của OpenCV) sang RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img_rgb


def rgb_to_grayscale(img_rgb):
    """Chuyển đổi ảnh RGB sang ảnh Xám (Grayscale)."""
    return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)


def rgb_to_hsv(img_rgb):
    """Chuyển đổi ảnh RGB sang không gian màu HSV."""
    return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)


def print_dict(dict):
    """Hiện thị output ra terminal dạng Dict có cấu trúc đẹp hơn"""
    pprint(dict, width=120)
