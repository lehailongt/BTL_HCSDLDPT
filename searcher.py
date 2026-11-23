"""Tìm ảnh theo nội dung trên toàn bộ kho, dùng công thức đã chốt ở bước 4."""
from pathlib import Path
from time import perf_counter
from threading import Lock

from db_function import read_catalog
from feature_extractor import features_from_masks
from preprocess_image import preprocess_image
from similarity import Descriptor, Scale
from image_regions import decode_image
from source_filter import SourceIndex

SEARCH_PROFILE = {"calibration": "median", "hist_mode": "hs_mix", "shape_balance": True}


class FlowerCatalog:
    """Một phiên bản kho và các cận chuẩn hóa được tính trên đúng phiên bản đó."""

    def __init__(self, rows, profile=None):
        self.rows = tuple(rows)
        self.scale = Scale.fit((row[3] for row in self.rows),
                               **(SEARCH_PROFILE if profile is None else profile))
        self._sources = None
        self._source_lock = Lock()

    @classmethod
    def load(cls):
        return cls(read_catalog())

    def rank(self, query, top_k=5, exclude_id=None, exclude_ids=()):
        if top_k < 1:
            raise ValueError("Số ảnh cần lấy phải lớn hơn 0.")
        matches = []
        excluded = set(exclude_ids)
        excluded.add(exclude_id)
        for image_id, name, path, descriptor in self.rows:
            if image_id not in excluded:
                scores = self.scale.compare(query, descriptor)
                matches.append(dict(image_id=image_id, file_name=name, file_path=path, **scores))
        matches.sort(key=lambda r: (-r["similarity"], -r["coverage"], r["image_id"]))
        return matches[:top_k], len(matches)

    def source_matches(self, image):
        with self._source_lock:
            if self._sources is None:
                self._sources = SourceIndex(self.rows)
        return self._sources.matches(image)


def decode_query(jpeg):
    """Đưa ảnh truy vấn về kích thước của kho; giữ tỉ lệ và hướng giải mã."""
    return decode_image(jpeg)


def search_image(image, name, catalog, top_k=5, exclude_id=None,
                 calyx_status="unknown", exclude_same_source=True, stem_status="unknown"):
    """Nhận ảnh BGR chuẩn từ decode_query, trả cùng kết quả và phép đo đã dùng."""
    start = perf_counter()
    prep = preprocess_image(image, calyx_status=calyx_status,stem_status=stem_status)
    features = features_from_masks(prep, name)
    query = Descriptor.from_extracted(features)
    measured = perf_counter()
    excluded = catalog.source_matches(image) if exclude_same_source else set()
    filtered = perf_counter()
    hits, compared = catalog.rank(query, top_k, exclude_id, excluded)
    return {"matches": hits, "compared": compared, "descriptor": query,
            "masks": {key: prep[key] for key in ("flower_mask", "calyx_mask", "stem_mask", "valid_mask")},
            "calyx_status": prep.get('calyx_status',calyx_status),
            "stem_status": prep.get('stem_status',stem_status),
            "organ_provenance": prep.get('organ_provenance',{}),
            "calyx_reason": prep.get("calyx_reason", "unresolved"),
            "excluded_sources": [row[1] for row in catalog.rows if row[0] in excluded],
            "source_filter_ms": (filtered-measured)*1000,
            "extract_ms": (measured-start)*1000, "rank_ms": (perf_counter()-filtered)*1000}


def search(image_path, top_k=5):
    """API theo đường dẫn, trả danh sách đường dẫn ảnh như phiên bản đầu."""
    path = Path(image_path)
    image, _ = decode_query(path.read_bytes())
    result = search_image(image, path.name, FlowerCatalog.load(), top_k)
    return [item["file_path"] for item in result["matches"]]
