"""Nhận ra bản cùng nguồn bằng pixel hoặc điểm SIFT khớp hình học."""
import hashlib
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from image_regions import decode_image, valid_region


def signature(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    points, descriptors = cv2.SIFT_create(nfeatures=240).detectAndCompute(
        gray, valid_region(image))
    xy = np.array([p.pt for p in points], np.float32).reshape(-1, 2)
    return hashlib.sha256(image.tobytes()).digest(), xy, descriptors


def same_source(query, candidate):
    if query[0] == candidate[0]:
        return True
    _, q_points, q_desc = query
    _, c_points, c_desc = candidate
    if q_desc is None or c_desc is None or min(len(q_desc), len(c_desc)) < 10:
        return False
    pairs = cv2.BFMatcher().knnMatch(q_desc, c_desc, k=2)
    good = [a for a, b in pairs if a.distance < .7*b.distance]
    if len(good) < 10:
        return False
    q = np.array([q_points[m.queryIdx] for m in good])
    c = np.array([c_points[m.trainIdx] for m in good])
    transform, inliers = cv2.estimateAffinePartial2D(q, c, ransacReprojThreshold=2.5)
    if transform is None:
        return False
    keep = inliers.ravel().astype(bool)
    count = int(keep.sum())
    scale = np.hypot(transform[0, 0], transform[1, 0])
    return (count >= 10 and count/len(good) >= .65 and .2 <= scale <= 5
            and cv2.contourArea(cv2.convexHull(q[keep])) >= 100
            and cv2.contourArea(cv2.convexHull(c[keep])) >= 100)


@lru_cache(maxsize=2048)
def file_signature(path, modified_ns, size):
    """Tái sử dụng điểm ảnh khi CSDL đổi nhưng tệp ảnh vẫn là phiên bản cũ."""
    image, _ = decode_image(Path(path).read_bytes())
    return signature(image)


class SourceIndex:
    def __init__(self, rows):
        self.entries = {}
        for image_id, _, path, _ in rows:
            path = Path(path)
            if not path.is_absolute():
                path = Path(__file__).resolve().parent / path
            info = path.stat()
            self.entries[image_id] = file_signature(str(path), info.st_mtime_ns, info.st_size)

    def matches(self, image):
        query = signature(image)
        return {image_id for image_id, entry in self.entries.items()
                if same_source(query, entry)}
