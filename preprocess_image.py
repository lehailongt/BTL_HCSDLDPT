# TIỀN XỬ LÝ
import cv2
import numpy as np


def create_background_mask(img_gray, threshold=240):
    """Mask nền sáng: 255 = nền, 0 = đối tượng."""
    _, mask = cv2.threshold(img_gray, threshold, 255, cv2.THRESH_BINARY)
    return mask


def _fill_holes(mask):
    h, w = mask.shape
    flood = mask.copy()
    m2 = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, m2, (0, 0), 255)
    return cv2.bitwise_or(mask, cv2.bitwise_not(flood))


def _largest_component(mask):
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num <= 1:
        return mask
    idx = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    out = np.zeros_like(mask)
    out[labels == idx] = 255
    return out


def preprocess_image(img_bgr):
    """
    Trả về dict: bgr, hsv, flower_mask, stem_mask, calyx_mask,
                 green_mask, obj_mask.
    """
    h, w = img_bgr.shape[:2]
    img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H, S, V = cv2.split(img_hsv)

    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bg_mask = create_background_mask(img_gray, threshold=240)
    obj_mask = cv2.bitwise_not(bg_mask)

    # màu xanh lá (cuống, lá, đài)
    green_lower = np.array([35, 60, 40])
    green_upper = np.array([90, 255, 255])
    green_mask = cv2.inRange(img_hsv, green_lower, green_upper)
    green_mask = cv2.bitwise_and(green_mask, obj_mask)

    # mask hoa = đối tượng - xanh - tối
    flower_mask = cv2.bitwise_and(obj_mask, cv2.bitwise_not(green_mask))
    dark_mask = (V < 30).astype(np.uint8) * 255
    flower_mask = cv2.bitwise_and(flower_mask, cv2.bitwise_not(dark_mask))
    flower_mask = cv2.morphologyEx(
        flower_mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    flower_mask = _fill_holes(flower_mask)
    flower_mask = _largest_component(flower_mask)

    if cv2.countNonZero(flower_mask) < 0.02 * h * w:
        flower_mask = _largest_component(obj_mask)

    # cuống: xanh ở nửa dưới
    stem_mask = green_mask.copy()
    stem_mask[: h // 2, :] = 0
    stem_mask = _largest_component(stem_mask)

    # đài: xanh ngay dưới đáy bông
    ys_f, _ = np.where(flower_mask > 0)
    if len(ys_f) > 0:
        bottom = int(np.max(ys_f))
        band = np.zeros_like(flower_mask)
        y0 = bottom
        y1 = min(h, bottom + int(0.25 * h))
        band[y0:y1, :] = 255
        calyx_mask = cv2.bitwise_and(green_mask, band)
        calyx_mask = _largest_component(calyx_mask)
    else:
        calyx_mask = np.zeros_like(flower_mask)

    return {
        "bgr": img_bgr,
        "hsv": img_hsv,
        "flower_mask": flower_mask,
        "stem_mask": stem_mask,
        "calyx_mask": calyx_mask,
        "green_mask": green_mask,
        "obj_mask": obj_mask,
    }
