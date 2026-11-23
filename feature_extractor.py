"""
extract_features.py
Trích xuất đặc trưng ảnh bông hoa theo 4 bộ thuộc tính:
  - Bộ 1: Màu sắc chủ đạo (HSV histogram, μ_H, μ_S, σ_H, σ_S, entropy, tỉ lệ màu chủ đạo, gradient S theo bán kính)
  - Bộ 2: Hình dạng tổng thể (diện tích, chu vi, độ tròn, aspect ratio, solidity, 7 Hu Moments)
  - Bộ 3: Đài hoa (tỉ lệ chiều dài lá đài, độ nhọn, mức bao sát, tỉ lệ diện tích đài/bông)
  - Bộ 4: Cuống hoa (độ dày cuống, tỉ lệ độ dày cuống / chiều rộng bông)

Yêu cầu: ảnh 256x256, 1 bông hoa ở giữa, chụp ngang.
"""

import cv2
import math
import numpy as np
from preprocess_image import preprocess_image
from utils import *


# ---------------------------------------------------------------------------
# 2. BỘ THUỘC TÍNH 1 – MÀU SẮC
# ---------------------------------------------------------------------------
def _hist_hsv_12x3x3(hsv, mask):
    """Histogram HSV 12H x 3S x 3V, chuẩn hóa tổng = 1."""
    pix = hsv[mask > 0]
    if pix.size == 0:
        return np.zeros(12 * 3 * 3, dtype=np.float32)
    hq = np.clip((pix[:, 0].astype(np.float32) / 180.0 * 12).astype(int), 0, 11)
    sq = np.clip((pix[:, 1].astype(np.float32) / 256.0 * 3).astype(int), 0, 2)
    vq = np.clip((pix[:, 2].astype(np.float32) / 256.0 * 3).astype(int), 0, 2)
    hist = np.bincount(hq * 9 + sq * 3 + vq, minlength=108).astype(np.float32)
    total = hist.sum()
    if total > 0:
        hist /= total
    return hist


def _gradient_s_vs_radius(hsv, mask):
    """
    Hệ số góc khi hồi quy tuyến tính S theo khoảng cách r từ pixel đến tâm bông.
    dS/dr > 0: đậm ở viền, nhạt ở tâm (hoa sen).
    dS/dr ≈ 0: màu đồng đều (hoa cánh bướm).
    """
    ys, xs = np.where(mask > 0)
    if len(ys) < 10:
        return 0.0
    cy, cx = ys.mean(), xs.mean()
    S = hsv[:, :, 1][mask > 0].astype(np.float32) / 255.0
    r = np.sqrt((ys - cy) ** 2 + (xs - cx) ** 2)
    r = r / (r.max() + 1e-8)
    # hồi quy tuyến tính S = a*r + b -> a = slope
    A = np.vstack([r, np.ones_like(r)]).T
    try:
        slope, _ = np.linalg.lstsq(A, S, rcond=None)[0]
    except np.linalg.LinAlgError:
        slope = 0.0
    return float(slope)


def circular_hue_stats(degrees):
    theta = np.deg2rad(np.asarray(degrees, dtype=float))
    c, s = np.cos(theta).mean(), np.sin(theta).mean()
    r = float(np.clip(np.hypot(c, s), 1e-12, 1.))
    mean = float(np.rad2deg(np.arctan2(s, c)) % 360) if r > 1e-6 else 0.
    return mean % 360, float(np.rad2deg(np.sqrt(-2*np.log(r))))


def extract_color_features(prep):
    hsv = prep["hsv"]
    mask = prep["flower_mask"]
    H, S, V = cv2.split(hsv)

    pix_mask = mask > 0
    n_pix = int(np.count_nonzero(pix_mask))
    if n_pix == 0:
        return {
            "hist_hsv": np.zeros(108, dtype=np.float32),
            "mu_H": 0.0,
            "mu_S": 0.0,
            "sigma_H": 0.0,
            "sigma_S": 0.0,
            "entropy_H": 0.0,
            "dominant_ratio": 0.0,
            "gradient_S_r": 0.0,
        }

    Hv = H[pix_mask].astype(np.float32) * 2.0  # OpenCV H 0-180 -> độ 0-360
    Sv = S[pix_mask].astype(np.float32) / 255.0

    mu_H, sigma_H = circular_hue_stats(Hv)
    mu_S = float(np.mean(Sv))
    sigma_S = float(np.std(Sv))

    # Entropy trên 12 vùng H
    hist_h = np.bincount(
        np.clip((Hv / 360.0 * 12).astype(int), 0, 11), minlength=12
    ).astype(np.float32)
    p = hist_h / hist_h.sum()
    p = p[p > 0]
    entropy_H = float(-np.sum(p * np.log2(p)))

    # Tỉ lệ diện tích màu chủ đạo (bin H lớn nhất)
    dominant_ratio = float(hist_h.max() / hist_h.sum())

    hist_hsv = _hist_hsv_12x3x3(hsv, mask)
    grad_S = _gradient_s_vs_radius(hsv, mask)

    return {
        "hist_hsv": hist_hsv,  # 108 chiều
        "mu_H": mu_H,  # 0-360
        "mu_S": mu_S,  # 0-1
        "sigma_H": sigma_H,
        "sigma_S": sigma_S,
        "entropy_H": entropy_H,
        "dominant_ratio": dominant_ratio,
        "gradient_S_r": grad_S,
    }


# ---------------------------------------------------------------------------
# 3. BỘ THUỘC TÍNH 2 – HÌNH DẠNG
# ---------------------------------------------------------------------------
def extract_shape_features(prep):
    mask = prep["flower_mask"]
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return {
            "area_ratio": 0.0,
            "perimeter": 0.0,
            "circularity": 0.0,
            "aspect_ratio": 0.0,
            "solidity": 0.0,
            "hu_moments": np.zeros(7, dtype=np.float32),
        }
    cnt = max(cnts, key=cv2.contourArea)
    area = float(cv2.countNonZero(mask))
    perim = float(len(cnt))  # CHAIN_APPROX_NONE giữ từng điểm biên ngoài.
    h_img, w_img = mask.shape
    area_ratio = area / (h_img * w_img)

    circularity = (4.0 * math.pi * area / (perim**2)) if perim > 0 else 0.0

    x, y, bw, bh = cv2.boundingRect(cnt)
    aspect_ratio = (bw / float(bh)) if bh > 0 else 0.0

    hull = cv2.convexHull(cnt)
    hull_mask = np.zeros_like(mask)
    cv2.fillConvexPoly(hull_mask, hull, 255)
    hull_area = float(cv2.countNonZero(hull_mask))
    solidity = (area / hull_area) if hull_area > 0 else 0.0

    moments = cv2.moments(mask, binaryImage=True)
    hu = cv2.HuMoments(moments).flatten()

    return {
        "area_ratio": area_ratio,
        "perimeter": perim,
        "circularity": circularity,
        "aspect_ratio": aspect_ratio,
        "solidity": solidity,
        "hu_moments": hu,
    }


# ---------------------------------------------------------------------------
# 4. BỘ THUỘC TÍNH 3 – ĐÀI HOA
# ---------------------------------------------------------------------------
def extract_calyx_features(prep):
    """Ước lượng chiều dài gốc–đỉnh và góc tại các đầu lá đài thấy được."""
    flower, calyx = prep["flower_mask"], prep["calyx_mask"]
    _, _, w, h = cv2.boundingRect(flower)
    diameter = max(w, h)
    ys, xs = np.where(calyx > 0)
    result = dict(sepal_length_ratio=0., sepal_sharpness=0.,
                  calyx_adhesion=0., calyx_area_ratio=0.)
    if not diameter or len(xs) < 5:
        return result

    # Gốc chung ước lượng tại vùng đài chuyển xuống cuống.
    bottom = ys.max()
    base = np.array([np.median(xs[ys >= bottom - 2]), bottom])
    if prep.get('calyx_attachment') and prep['stem_mask'].any():
        # For sideways/hanging detections, the root is the calyx point nearest
        # the stalk, rather than the lowest pixel in image coordinates.
        stem_distance=cv2.distanceTransform(np.uint8(prep['stem_mask']==0),cv2.DIST_L2,5)
        near=stem_distance[ys,xs]<=stem_distance[ys,xs].min()+2
        base=np.array([np.median(xs[near]),np.median(ys[near])])
    contours, _ = cv2.findContours(calyx, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    lengths, angles = [], []
    for cnt in contours:
        if cv2.contourArea(cnt) < 3:
            continue
        epsilon = max(1., .025 * cv2.arcLength(cnt, True))
        poly = cv2.approxPolyDP(cnt, epsilon, True).reshape(-1, 2).astype(float)
        if len(poly) < 3:
            continue
        radii = np.linalg.norm(poly - base, axis=1)
        for i, point in enumerate(poly):
            # Một đỉnh lá là cực đại cục bộ của khoảng cách tới gốc.
            j = (i + 1) % len(poly)
            if radii[i] <= radii[i-1] or radii[i] < radii[j] or radii[i] < 2:
                continue
            u, v = poly[i-1] - point, poly[j] - point
            cosine = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
            angle = math.degrees(math.acos(float(np.clip(cosine, -1., 1.))))
            if angle < 150:
                lengths.append(radii[i])
                angles.append(angle)

    if lengths:
        result["sepal_length_ratio"] = float(np.mean(lengths)) / diameter
        result["sepal_sharpness"] = float(np.mean(angles))
    distance = cv2.distanceTransform(np.uint8(flower == 0), cv2.DIST_L2,
                                     cv2.DIST_MASK_PRECISE)
    result["calyx_adhesion"] = float(distance[ys, xs].mean()) / diameter
    result["calyx_area_ratio"] = len(xs) / cv2.countNonZero(flower)
    return result


# ---------------------------------------------------------------------------
# 5. BỘ THUỘC TÍNH 4 – CUỐNG HOA
# ---------------------------------------------------------------------------
def extract_stem_features(prep):
    stem_mask = prep["stem_mask"]
    flower_mask = prep["flower_mask"]
    # A newly recovered sideways stem is measured in its detection frame.
    # Existing detections retain their original measurements.
    if prep.get('stem_measurement') is not None:
        stem_mask = prep['stem_measurement']['measurement_mask']
        flower_mask = prep['stem_measurement']['flower_mask']

    ys_s, xs_s = np.where(stem_mask > 0)
    if len(ys_s) < 5:
        return {"stem_thickness": 0.0, "stem_width_ratio": 0.0}

    stem_area = float(len(ys_s))
    y_min, y_max = ys_s.min(), ys_s.max()
    stem_len = float(y_max - y_min + 1)
    stem_thickness = stem_area / stem_len if stem_len > 0 else 0.0

    # chiều rộng bông
    bf = cv2.boundingRect(flower_mask)
    flower_width = float(bf[2]) if bf[2] > 0 else 0.0
    stem_width_ratio = (stem_thickness / flower_width) if flower_width > 0 else 0.0

    return {
        "stem_thickness": stem_thickness,
        "stem_width_ratio": stem_width_ratio,
    }


def extract_all_feature(file_path, calyx_status="unknown", stem_status="unknown"):
    """Trích xuất toàn bộ thuộc tính từ 1 file ảnh, trả về dict."""
    img = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Không đọc được ảnh: {file_path}")
    return features_from_masks(preprocess_image(img, calyx_status=calyx_status,stem_status=stem_status), file_path)


def features_from_masks(prep, file_path):
    """Dùng chung phép đo cho ảnh trong kho, ảnh minh họa và ảnh truy vấn."""
    if not cv2.countNonZero(prep["flower_mask"]):
        raise ValueError(f"Chưa phân đoạn được bông: {file_path}")
    feats = {"file": str(file_path)}
    feats["calyx_status"] = prep.get("calyx_status", "unknown")
    feats["stem_status"] = prep.get("stem_status", "unknown")
    feats["color"] = extract_color_features(prep)
    feats["shape"] = extract_shape_features(prep)
    feats["calyx"] = extract_calyx_features(prep)
    feats["stem"] = extract_stem_features(prep)
    return feats
