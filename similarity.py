"""Bước 4: chuẩn hóa theo kho ảnh và tính điểm tương đồng của một cặp."""
from dataclasses import dataclass, field
import json

import numpy as np


COLOR = ("mean_h", "mean_s", "std_h", "std_s", "entropy",
         "dominant_color_ratio", "gradient_s_radius")
SHAPE = ("area", "perimeter", "circularity", "aspect_ratio", "solidity",
         *(f"hu_moment_{i}" for i in range(1, 8)))
CALYX = ("sepal_length_ratio", "sepal_sharpness", "calyx_adhesion", "calyx_area_ratio")
STEM = ("stem_thickness", "stem_width_ratio")
FIELDS = COLOR + SHAPE + CALYX + STEM
WEIGHTS = {"color": .40, "shape": .30, "calyx": .20, "stem": .10}
GROUPS = {name: [FIELDS.index(k) for k in fields] for name, fields in
          (("color", COLOR), ("shape", SHAPE), ("calyx", CALYX), ("stem", STEM))}


@dataclass
class Descriptor:
    hist: np.ndarray
    values: np.ndarray
    calyx_status: str = "unknown"
    stem_status: str = "unknown"

    def __post_init__(self):
        h = np.asarray(self.hist, dtype=float)
        v = np.array(self.values, dtype=float, copy=True)
        if h.shape != (108,) or not np.isfinite(h).all() or (h < 0).any() or abs(h.sum()-1) > 1e-6:
            raise ValueError("Histogram HSV phải có 108 số không âm, tổng bằng 1")
        if v.shape != (len(FIELDS),) or not np.isfinite(v).all():
            raise ValueError("Cần đủ 25 số đo hữu hạn ngoài histogram")
        if not 0 <= v[0] < 360:
            raise ValueError("H trung bình phải thuộc [0, 360)")
        # Chỉ diễn giải các số 0 mang nghĩa thiếu quan sát theo bộ trích rút phần 3.
        if self.calyx_status not in ("unknown", "present", "absent", "unobservable"):
            raise ValueError("Invalid calyx status")
        if self.stem_status not in ("unknown", "present", "absent", "unobservable"):
            raise ValueError("Invalid stem status")
        if v[FIELDS.index("std_h")] >= np.rad2deg(np.sqrt(-2*np.log(1e-6))):
            v[0] = np.nan  # Hue direction is not defined for a near-zero resultant.
        if self.calyx_status == "absent":
            v[GROUPS["calyx"]] = np.nan
            v[FIELDS.index("calyx_area_ratio")] = 0.
        elif self.calyx_status == "unobservable" or v[FIELDS.index("calyx_area_ratio")] == 0:
            v[GROUPS["calyx"]] = np.nan
        elif v[FIELDS.index("sepal_length_ratio")] == 0:
            v[GROUPS["calyx"][:2]] = np.nan
        if self.stem_status in ('absent','unobservable') or v[FIELDS.index("stem_thickness")] == 0:
            v[GROUPS["stem"]] = np.nan
        self.hist, self.values = h / h.sum(), v

    @classmethod
    def from_row(cls, row):
        hist = row["hist_hsv"]
        if isinstance(hist, (str, bytes, bytearray)):
            hist = json.loads(hist)
        return cls(hist, [row[k] for k in FIELDS], row.get("calyx_status") or "unknown",row.get('stem_status') or 'unknown')

    @classmethod
    def from_extracted(cls, features):
        color, shape = features["color"], features["shape"]
        values = [color[k] for k in ("mu_H", "mu_S", "sigma_H", "sigma_S",
                                      "entropy_H", "dominant_ratio", "gradient_S_r")]
        values += [shape[k] for k in ("area_ratio", *SHAPE[1:5])]
        values.extend(shape["hu_moments"])
        values.extend(features["calyx"][k] for k in CALYX)
        values.extend(features["stem"][k] for k in STEM)
        return cls(color["hist_hsv"], values, features.get("calyx_status", "unknown"),features.get('stem_status','unknown'))

    def organ_state(self, group):
        status = getattr(self,group+'_status')
        if status == 'absent':
            return 'Không có (đã xác nhận)'
        if status == 'unobservable':
            return 'Không quan sát được (đã xác nhận)'
        if np.isfinite(self.values[GROUPS[group]]).any():
            return 'Có vùng đo tự động' if status == 'unknown' else 'Có (đã xác nhận, đã đo)'
        return 'Có (đã xác nhận), chưa đo được' if status == 'present' else 'Chưa xác định'


@dataclass
class Scale:
    low: np.ndarray
    high: np.ndarray
    counts: np.ndarray
    factors: dict = field(default_factory=dict)
    hist_mode: str = "raw"
    shape_balance: bool = False
    pair_counts: dict = field(default_factory=dict)

    @classmethod
    def fit(cls, catalog, calibration=None, hist_mode="raw", shape_balance=False):
        """Chỉ gọi trên tập tham chiếu. Mỗi cột chỉ dùng các phép đo có mặt."""
        catalog = list(catalog)
        matrix = np.array([d.values for d in catalog])
        if not len(matrix):
            raise ValueError("Kho tham chiếu rỗng")
        low, high = np.zeros(len(FIELDS)), np.zeros(len(FIELDS))
        counts = np.isfinite(matrix).sum(axis=0)
        for i, col in enumerate(matrix.T):
            observed = col[np.isfinite(col)]
            if observed.size:
                low[i], high[i] = np.quantile(observed, [.01, .99], method="linear")
                if low[i] == high[i]:
                    low[i], high[i] = observed.min(), observed.max()
        # Với sắc màu, so góc theo chu kỳ 360° trên miền vật lý.
        if high[0] > low[0]:
            low[0], high[0] = 0, 360
        scale = cls(low, high, counts, hist_mode=hist_mode, shape_balance=shape_balance)
        if calibration is not None and len(catalog) >= 20:
            if calibration not in ("median", "p90"):
                raise ValueError("Invalid group calibration")
            rng = np.random.default_rng(20261122)
            samples = {g: [] for g in GROUPS}
            for _ in range(3000):
                i, j = rng.choice(len(catalog), 2, replace=False)
                result = scale.compare(catalog[i], catalog[j])
                for g, d in result['distances'].items():
                    if d is not None:
                        samples[g].append(d)
            scale.pair_counts = {g: len(v) for g,v in samples.items()}
            scale.factors = {g: max(1e-6, float(np.quantile(v, .5 if calibration=='median' else .9)))
                             if len(v)>=50 and np.any(v) else 1. for g,v in samples.items()}
        return scale

    def normalize(self, descriptor):
        span = self.high - self.low
        z = np.full(len(FIELDS), np.nan)
        np.divide(descriptor.values - self.low, span, out=z, where=span > 0)
        return np.clip(z, 0, 1)

    def compare(self, a, b):
        delta = np.abs(self.normalize(a) - self.normalize(b))
        delta[0] = 2 * np.minimum(delta[0], 1 - delta[0])  # cung ngắn / 180°
        hist_distance = float(np.abs(a.hist - b.hist).sum() / 2)
        if self.hist_mode == "hs_mix":
            ha, hb = a.hist.reshape(12,3,3), b.hist.reshape(12,3,3)
            hist_distance = .5*hist_distance + .5*float(np.abs(ha.sum(axis=2)-hb.sum(axis=2)).sum()/2)
        elif self.hist_mode != "raw":
            raise ValueError("Invalid histogram mode")
        distances, raw_weights = {}, {}
        for group, indexes in GROUPS.items():
            diffs = delta[indexes]
            common = diffs[np.isfinite(diffs)]
            rms = float(np.sqrt(np.mean(common ** 2))) if common.size else None
            if group == "shape" and self.shape_balance:
                parts = [diffs[[2,3,4]], diffs[[0,1,5,6,7,8,9,10,11]]]
                means = [np.mean(p[np.isfinite(p)]**2) for p in parts if np.isfinite(p).any()]
                rms = float(np.sqrt(np.mean(means))) if means else None
            if group == "color":
                distances[group] = (hist_distance + rms) / 2 if rms is not None else hist_distance
                raw_weights[group] = WEIGHTS[group]
            else:
                distances[group] = rms
                usable = np.count_nonzero(self.high[indexes] > self.low[indexes])
                raw_weights[group] = WEIGHTS[group] * common.size / usable if usable else 0.
        confirmed = a.calyx_status in ('present','absent') and b.calyx_status in ('present','absent')
        state_comparison = confirmed and 'absent' in (a.calyx_status,b.calyx_status)
        if state_comparison:
            distances['calyx'] = float(a.calyx_status != b.calyx_status)
            raw_weights['calyx'] = WEIGHTS['calyx']
        elif 'absent' in (a.calyx_status,b.calyx_status):
            distances['calyx'], raw_weights['calyx'] = None, 0.
        stem_confirmed = a.stem_status in ('present','absent') and b.stem_status in ('present','absent')
        stem_state_comparison = stem_confirmed and 'absent' in (a.stem_status,b.stem_status)
        if stem_state_comparison:
            distances['stem'] = float(a.stem_status != b.stem_status)
            raw_weights['stem'] = WEIGHTS['stem']
        raw_distances = dict(distances)
        comparisons = {'calyx':state_comparison, 'stem':stem_state_comparison}
        factors = {g: (1. if comparisons.get(g,False) else self.factors.get(g,1.)) for g in GROUPS}
        distances = {g: None if d is None else d/factors[g] for g,d in distances.items()}
        coverage = sum(raw_weights.values())
        weights = {key: w / coverage for key, w in raw_weights.items()}
        total = sum(weights[k] * d for k, d in distances.items() if d is not None)
        total = float(max(total, 0))
        missing_reason = {}
        for group,indexes in GROUPS.items():
            if distances[group] is not None:
                continue
            qa = np.isfinite(a.values[indexes]).any()
            qb = np.isfinite(b.values[indexes]).any()
            if group=='stem' and 'absent' in (a.stem_status,b.stem_status):
                side = 'Cả hai ảnh' if a.stem_status == b.stem_status else 'Ảnh truy vấn' if a.stem_status=='absent' else 'Ảnh kết quả'
                reason = side+': không có cuống (đã xác nhận)'
            elif group=='calyx' and 'absent' in (a.calyx_status,b.calyx_status):
                reason = "Trạng thái đài chưa đủ xác nhận ở hai ảnh"
            elif not qa and not qb:
                reason = "Cả truy vấn và kết quả chưa đo được"
            elif not qa:
                reason = "Ảnh truy vấn chưa đo được"
            elif not qb:
                reason = "Ảnh kết quả chưa đo được"
            else:
                reason = "Không có cột biến thiên dùng chung"
            missing_reason[group] = reason
        return {"hist_distance": hist_distance, "distances": distances, "weights": weights,
                "coverage": coverage, "total_distance": total, "similarity": 1 / (1 + total),
                "raw_distances": raw_distances, "group_factors": factors,
                "calyx_state_comparison": state_comparison, "missing_reason": missing_reason,
                "organ_state_comparisons": comparisons,
                "organ_states": {g:b.organ_state(g) for g in ('calyx','stem')}}
