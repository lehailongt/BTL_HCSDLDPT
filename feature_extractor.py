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
    hist = np.zeros(12 * 3 * 3, dtype=np.float32)
    for h_, s_, v_ in zip(hq, sq, vq):
        hist[int(max(h_ * 9 + s_ * 3 + v_, 1))] += 1
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

    mu_H = float(np.mean(Hv))
    mu_S = float(np.mean(Sv))
    sigma_H = float(np.std(Hv))
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
    area = float(cv2.contourArea(cnt))
    perim = float(cv2.arcLength(cnt, True))
    h_img, w_img = mask.shape
    area_ratio = area / (h_img * w_img)

    circularity = (4.0 * math.pi * area / (perim**2)) if perim > 0 else 0.0

    x, y, bw, bh = cv2.boundingRect(cnt)
    aspect_ratio = (bw / float(bh)) if bh > 0 else 0.0

    hull = cv2.convexHull(cnt)
    hull_area = float(cv2.contourArea(hull))
    solidity = (area / hull_area) if hull_area > 0 else 0.0

    moments = cv2.moments(mask, binaryImage=True)
    hu = cv2.HuMoments(moments).flatten()
    # log-transform để giảm range
    hu_log = np.sign(hu) * np.log10(np.abs(hu) + 1e-30)

    return {
        "area_ratio": area_ratio,
        "perimeter": perim,
        "circularity": circularity,
        "aspect_ratio": aspect_ratio,
        "solidity": solidity,
        "hu_moments": hu_log.astype(np.float32),  # 7 chiều
    }


# ---------------------------------------------------------------------------
# 4. BỘ THUỘC TÍNH 3 – ĐÀI HOA
# ---------------------------------------------------------------------------
def extract_calyx_features(prep):
    """
    Bộ 3 – Lá đài / Đài hoa (khớp schema DB):
      - sepal_length_ratio : chiều dài lá đài / đường kính bông
      - sepal_sharpness    : độ nhọn lá đài (0..90, càng lớn càng nhọn)
      - calyx_adhesion     : mức bám đài vào bông (0..1, càng lớn càng sát)
      - calyx_area_ratio   : diện tích đài / diện tích bông (0..1)
    """
    flower_mask = prep["flower_mask"]
    calyx_mask = prep["calyx_mask"]

    empty = {
        "sepal_length_ratio": 0.0,
        "sepal_sharpness": 0.0,
        "calyx_adhesion": 0.0,
        "calyx_area_ratio": 0.0,
    }

    ys_f, xs_f = np.where(flower_mask > 0)
    if len(ys_f) == 0:
        return empty

    # --- Đường kính bông ---
    bf = cv2.boundingRect(flower_mask)
    D = float(max(bf[2], bf[3]))
    if D <= 0:
        return empty
    S_flower = float(np.count_nonzero(flower_mask))

    # Tâm bbox bông (ổn định hơn centroid khi hoa lệch)
    cx = bf[0] + bf[2] / 2.0
    cy = bf[1] + bf[3] / 2.0

    cnts, _ = cv2.findContours(calyx_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return empty

    calyx_ys, calyx_xs = np.where(calyx_mask > 0)
    if len(calyx_ys) < 5:
        return empty

    # ------------------------------------------------------------------
    # 1) SEPAL LENGTH: PCA trên toàn bộ pixel đài → chiều dài trục chính
    #    (ổn định với mọi hướng xòe của lá đài)
    # ------------------------------------------------------------------
    pts = np.column_stack([calyx_xs, calyx_ys]).astype(np.float32)
    pts_c = pts - pts.mean(axis=0)
    cov = np.cov(pts_c.T)
    try:
        eigvals, eigvecs = np.linalg.eigh(cov)
        major = eigvecs[:, np.argmax(eigvals)]
        proj = pts_c @ major
        sepal_len = float(proj.max() - proj.min())
    except np.linalg.LinAlgError:
        dx = pts[:, 0] - cx
        dy = pts[:, 1] - cy
        sepal_len = float(np.sqrt(dx * dx + dy * dy).max())

    sepal_length_ratio = float(np.clip(sepal_len / D, 0.0, 1.0))

    # ------------------------------------------------------------------
    # 2) SEPAL SHARPNESS: góc nhọn nhất tại đỉnh lá đài
    #    → 0° = rất nhọn → sharpness = 90; 90° = tù → sharpness = 0
    # ------------------------------------------------------------------
    cnt = max(cnts, key=cv2.contourArea)
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    angles = []
    n = len(approx)
    if n >= 3:
        for i in range(n):
            p0 = approx[i][0].astype(np.float64)
            p1 = approx[(i - 1) % n][0].astype(np.float64)
            p2 = approx[(i + 1) % n][0].astype(np.float64)
            v1 = p1 - p0
            v2 = p2 - p0
            n1 = np.linalg.norm(v1)
            n2 = np.linalg.norm(v2)
            if n1 < 1e-6 or n2 < 1e-6:
                continue
            cos_a = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
            angles.append(math.degrees(math.acos(cos_a)))

    if angles:
        sharp = [a for a in angles if a < 90.0]
        min_angle = float(min(sharp) if sharp else min(angles))
        sepal_sharpness = float(np.clip(90.0 - min_angle, 0.0, 90.0))
    else:
        sepal_sharpness = 0.0

    # ------------------------------------------------------------------
    # 3) CALYX ADHESION: 1 - (khoảng cách TB đài→bông / D)
    #    càng sát bông → adhesion càng gần 1
    # ------------------------------------------------------------------
    dist_to_flower = cv2.distanceTransform(
        (flower_mask > 0).astype(np.uint8), cv2.DIST_L2, 5
    )
    d_vals = dist_to_flower[calyx_ys, calyx_xs]
    mean_d_norm = float(np.mean(d_vals)) / D
    calyx_adhesion = float(np.clip(1.0 - mean_d_norm, 0.0, 1.0))

    # ------------------------------------------------------------------
    # 4) CALYX AREA RATIO: diện tích đài / diện tích bông
    # ------------------------------------------------------------------
    calyx_area = float(len(calyx_ys))
    calyx_area_ratio = calyx_area / S_flower if S_flower > 0 else 0.0
    calyx_area_ratio = float(np.clip(calyx_area_ratio, 0.0, 1.0))

    return {
        "sepal_length_ratio": sepal_length_ratio,
        "sepal_sharpness": sepal_sharpness,
        "calyx_adhesion": calyx_adhesion,
        "calyx_area_ratio": calyx_area_ratio,
    }


# ---------------------------------------------------------------------------
# 5. BỘ THUỘC TÍNH 4 – CUỐNG HOA
# ---------------------------------------------------------------------------
def extract_stem_features(prep):
    stem_mask = prep["stem_mask"]
    flower_mask = prep["flower_mask"]

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


def extract_all_feature(file_path):
    """Trích xuất toàn bộ thuộc tính từ 1 file ảnh, trả về dict."""
    img = cv2.imread(file_path)
    if img is None:
        raise FileNotFoundError(f"Không đọc được ảnh: {file_path}")
    img_bgr = img
    prep = preprocess_image(img_bgr)

    feats = {}
    feats["file"] = file_path
    feats["color"] = extract_color_features(prep)
    feats["shape"] = extract_shape_features(prep)
    feats["calyx"] = extract_calyx_features(prep)
    feats["stem"] = extract_stem_features(prep)
    return feats
