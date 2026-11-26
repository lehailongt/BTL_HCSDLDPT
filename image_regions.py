"""Vùng ảnh thật và chuẩn hóa kích thước, dùng chung cho kho và truy vấn."""
import cv2
import numpy as np


def repeated_edge(lines):
    """Ước lượng dải lặp từ mép có hoa văn; nền phẳng không đủ bằng chứng."""
    reference = lines[0].astype(np.float32)
    if reference.std(axis=0).mean() < 6:
        return 0
    count = 0
    for line in lines[1:len(lines)//2]:
        difference = np.abs(line.astype(np.float32) - reference)
        if difference.mean() > 1.0 or np.quantile(difference, .95) > 3:
            break
        count += 1
    return count if count >= 3 else 0


def valid_region(image, padding=None):
    h, w = image.shape[:2]
    if padding is None:
        columns = image.swapaxes(0, 1)
        padding = (repeated_edge(image), repeated_edge(image[::-1]),
                   repeated_edge(columns), repeated_edge(columns[::-1]))
    top, bottom, left, right = map(int, padding)
    if min(top, bottom, left, right) < 0 or top + bottom >= h or left + right >= w:
        raise ValueError("Kích thước viền thêm không hợp lệ.")
    mask = np.zeros((h, w), np.uint8)
    mask[top:h-bottom, left:w-right] = 255
    return mask


def decode_image(data):
    if not data:
        raise ValueError("Tệp ảnh rỗng.")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Không đọc được nội dung ảnh.")
    h, w = image.shape[:2]
    if min(h, w) < 8:
        raise ValueError("Ảnh quá nhỏ để tách vùng bông.")
    scale = 256 / max(h, w)
    width, height = max(1, round(w*scale)), max(1, round(h*scale))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    image = cv2.resize(image, (width, height), interpolation=interpolation)
    top, left = (256-height)//2, (256-width)//2
    image = cv2.copyMakeBorder(image, top, 256-height-top, left, 256-width-left,
                               cv2.BORDER_REPLICATE)
    return image, (w, h)
