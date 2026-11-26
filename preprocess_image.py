"""Phân vùng các bộ phận trên ảnh hoa đã chuẩn bị của nhóm."""
import cv2
import numpy as np
from image_regions import valid_region
from organ_regions import multi_direction_stem, attachment_calyx, supported_stem, calyx_collar


def _center_component(mask):
    """Ưu tiên vùng đủ lớn, nằm gần tâm bông trong khung ảnh."""
    h, w = mask.shape
    n, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    if n == 1:
        return np.zeros_like(mask)
    offset = (centers[1:] - [w * .5, h * .43]) / [w, h]
    scores = stats[1:, cv2.CC_STAT_AREA] / (1 + 12 * (offset ** 2).sum(axis=1))
    return np.uint8(labels == 1 + scores.argmax()) * 255


def _flower_component(mask):
    """Cắt cầu nối mảnh, chọn bông chính rồi phục hồi mép trong lân cận nhỏ."""
    size = max(3, round(min(mask.shape) / 28) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    core = _center_component(cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel))
    if cv2.countNonZero(core) < .75 * cv2.countNonZero(_center_component(mask)):
        return _center_component(mask)
    nearby = cv2.dilate(core, kernel)
    return _center_component(cv2.bitwise_and(mask, nearby))


def _stem_below(green, start, center, width):
    """Lần theo đoạn xanh hẹp gần trục cuống từ trên xuống."""
    result = np.zeros_like(green)
    gap = 0
    for y in range(start, len(green)):
        positions = np.flatnonzero(green[y])
        runs = np.split(positions, np.flatnonzero(np.diff(positions) > 1) + 1)
        candidates = []
        for run in runs:
            if not 1 <= len(run) <= max(4, width * .22):
                continue
            midpoint = (int(run[0]) + int(run[-1])) / 2
            if abs(midpoint - center) <= max(4, width * .12):
                candidates.append((abs(midpoint - center), midpoint, run))
        if candidates:
            _, center, run = min(candidates, key=lambda item: item[0])
            result[y, run] = 255
            gap = 0
        else:
            gap += 1
            if gap > max(4, width * .08):
                break
    return result


def _attached_stem(plant, flower, width):
    """Dò từ điểm gần bông theo cả hai chiều, chọn đoạn cuống liên tục dài nhất."""
    clean = plant.copy()
    clean[flower > 0] = 0
    distance = cv2.distanceTransform(cv2.bitwise_not(flower), cv2.DIST_L2, 5)
    best, best_score = np.zeros_like(plant), 0.
    x, y, bw, bh = cv2.boundingRect(flower)
    # Giữ đường dò từ gốc dưới cho bông đứng; ngưỡng quá chặt ở đường
    # hai chiều sẽ bỏ cuống ngắn hoặc đoạn cuống bị lá che một phần.
    base = flower[max(y, y+bh-round(.28*bh)):y+bh]
    center = float(np.median(np.where(base)[1]))
    candidates = []
    for row in range(y+bh, min(len(plant), y+bh+max(3, round(.12*bw))+1)):
        xs = np.flatnonzero(clean[row])
        for run in np.split(xs, np.flatnonzero(np.diff(xs) > 1)+1):
            if 2 <= len(run) <= max(4, .22*bw):
                mid = float(run.mean())
                if abs(mid-center) <= .25*bw:
                    candidates.append((abs(mid-center), row, mid))
    lower_best, lower_length = None, 0
    for _, row, mid in sorted(candidates):
        trace = _stem_below(clean, row, mid, width)
        ys, xs = np.where(trace)
        length = ys.max()-ys.min()+1 if len(ys) else 0
        if length >= max(5, .06*bw) and length > lower_length:
            lower_best, lower_length = trace, length
    if lower_best is not None:
        return lower_best
    # Không dò các hàng giữa bông để tránh lấy lá bên cạnh làm cuống.
    for reverse in (False, True):
        work = clean[::-1] if reverse else clean
        dist = distance[::-1] if reverse else distance
        edge = len(plant) - y if reverse else y + bh
        tip = flower[y:y+max(2, round(.06*bh))] if reverse else flower[y+bh-max(2, round(.06*bh)):y+bh]
        anchor = float(np.median(np.where(tip)[1]))
        starts = range(max(0, edge),
                       min(len(work), edge + max(4, round(.3 * width))))
        seeds = []
        for row in starts:
            xs = np.flatnonzero(work[row])
            for run in np.split(xs, np.flatnonzero(np.diff(xs) > 1) + 1):
                if not 2 <= len(run) <= max(4, .22 * width):
                    continue
                mid = float(run.mean())
                proximity = float(dist[row, run].min())
                if abs(mid-anchor) <= .25*bw and proximity <= max(3, .04*width):
                    seeds.append((proximity, row, mid))
        # Một điểm bắt đầu cho mỗi vùng gần nhau để hạn chế lặp phép dò.
        used = set()
        for proximity, row, mid in sorted(seeds):
            key = (row // 5, int(mid) // 5)
            if key in used:
                continue
            used.add(key)
            trace = _stem_below(work, row, mid, width)
            ys, xs = np.where(trace)
            if not len(ys):
                continue
            length = ys.max() - ys.min() + 1
            occupied = np.unique(ys).size
            thickness = len(xs) / occupied
            if length < max(8, .12*width) or occupied / length < .7 or length < 2*thickness:
                continue
            score = occupied / (1 + proximity / max(4, .08*width))
            if score > best_score:
                best, best_score = (trace[::-1].copy() if reverse else trace), score
    return best


def _edge_stem(image, flower, valid, start_offset=0, min_slenderness=3, shadow_edges=False, anchor=None):
    """Fallback: track opposite horizontal gradients near the flower attachment."""
    out = np.zeros_like(flower)
    x,y,bw,bh = cv2.boundingRect(flower)
    if not bw or not bh:
        return out
    base = flower[y+bh-max(2,round(.2*bh)):y+bh]
    center = float(np.median(np.where(base)[1]))
    if anchor is not None:
        center = anchor
    gray = cv2.GaussianBlur(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(3,3),0)
    gx = cv2.Sobel(gray,cv2.CV_32F,1,0,ksize=3)/4
    green = cv2.inRange(cv2.cvtColor(image,cv2.COLOR_BGR2HSV),(20,24,10),(95,255,255))
    gap, started, previous_width = 0, False, None
    for row in range(y+bh+start_offset, len(flower)):
        reach = max(5, .12*bw) if not started else max(3, .04*bw)
        edges = np.flatnonzero((np.abs(gx[row])>=10)&(valid[row]>0))
        if shadow_edges:
            strength=np.abs(gx[row])
            edges=np.array([p for p in edges if strength[p]>=strength[max(0,p-2):p+3].max()])
        choices=[]
        for left in edges:
            for right in edges[(edges>=left+2)&(edges<=left+max(4,.16*bw))]:
                mid=(left+right)/2; width=right-left
                if abs(mid-center)>reach or (not shadow_edges and gx[row,left]*gx[row,right]>=0):
                    continue
                if shadow_edges and width < max(4,.035*bw):
                    continue
                if previous_width and not .5*previous_width<=width<=1.8*previous_width:
                    continue
                if np.mean(green[row,left:right+1]>0)<.7 or not valid[row,left:right+1].all():
                    continue
                score=min(abs(gx[row,left]),abs(gx[row,right]))/(1+abs(mid-center))
                choices.append((score,left,right,mid,width))
        if choices:
            _,left,right,center,previous_width=max(choices)
            out[row,left:right+1]=255;gap=0;started=True
        else:
            gap+=1
            if gap> (max(4,.12*bw) if not started else 3):
                break
    ys,xs=np.where(out)
    if len(ys):
        height=ys.max()-ys.min()+1; occupied=np.unique(ys).size
        if height>=max(12,.15*bw) and occupied/height>=.8 and height>=min_slenderness*len(xs)/occupied:
            return out
    return np.zeros_like(out)


def _validate_calyx(calyx, flower, foreground):
    """Chỉ giữ ứng viên tiền cảnh đủ diện tích và tiếp xúc rõ với gốc bông."""
    accepted = np.zeros_like(calyx)
    x, y, bw, bh = cv2.boundingRect(flower)
    if not bw or not bh:
        return accepted
    distance = cv2.distanceTransform(cv2.bitwise_not(flower), cv2.DIST_L2, 5)
    base = flower[y+bh-max(2, round(.15*bh)):y+bh]
    axis = float(np.median(np.where(base)[1]))
    n, labels, stats, centers = cv2.connectedComponentsWithStats(calyx)
    for label in range(1, n):
        cx, cy, cw, ch, area = stats[label]
        component = labels == label
        if (area >= max(8, .001*cv2.countNonZero(flower))
                and np.mean(foreground[component] > 0) >= .8
                and np.count_nonzero(distance[component] <= 2) >= 3
                and abs(centers[label, 0]-axis) <= .3*bw
                and cy+ch >= y+.75*bh
                and cw >= max(3, .05*bw)):
            accepted[component] = 255
    return accepted


def preprocess_image(img_bgr, calyx_status="unknown", padding=None, stem_status="unknown", use_annotations=True):
    h, w = img_bgr.shape[:2]
    if min(h, w) < 8:
        raise ValueError("Ảnh quá nhỏ để phân vùng bông.")
    if calyx_status not in ("unknown", "present", "absent", "unobservable"):
        raise ValueError("Trạng thái đài không hợp lệ.")
    if stem_status not in ("unknown", "present", "absent", "unobservable"):
        raise ValueError("Trạng thái cuống không hợp lệ.")
    valid = valid_region(img_bgr, padding)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # Gán nền ở mép, ước lượng tiền cảnh trung tâm bằng màu và tính liên thông.
    mx, my = max(1, w // 32), max(1, h // 32)
    labels = np.zeros((h, w), np.uint8)
    cv2.setRNGSeed(10)
    cv2.grabCut(img_bgr, labels, (mx, my, w-2*mx, h-2*my),
                np.zeros((1, 65)), np.zeros((1, 65)), 3, cv2.GC_INIT_WITH_RECT)
    obj = np.uint8(labels % 2) * 255
    obj &= valid
    green = cv2.inRange(hsv, (30, 40, 25), (90, 255, 255))
    # Chỉ loại màu xanh đủ rõ. Vùng vàng nhạt/ít bão hòa có thể là
    # cánh trắng trong bóng hoặc phản sáng, không phải lá/cuống.
    petals = cv2.bitwise_and(obj, cv2.bitwise_not(green))
    petals[hsv[:, :, 2] < 30] = 0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    flower = _flower_component(petals)
    if cv2.countNonZero(flower) < .015 * h * w:
        # Trường hợp GrabCut hòa bông vào nền: lấy vùng màu cánh gần tâm.
        seed = cv2.inRange(hsv, (0, 55, 45), (179, 255, 255))
        seed[green > 0] = 0
        seed &= valid
        flower = _flower_component(seed)

    calyx = np.zeros((h, w), np.uint8)
    stem = np.zeros_like(calyx)
    x, y, bw, bh = cv2.boundingRect(flower)
    if bw and bh:
        bottom = y + bh
        base_y = max(y, bottom - max(2, round(.28 * bh)))
        _, base_xs = np.where(flower[base_y:bottom] > 0)
        center = float(np.median(base_xs))
        half = max(3, round(.45 * bw))
        left, right = max(0, int(center)-half), min(w, int(center)+half+1)
        end = min(h, bottom + max(2, round(.12 * bw)))
        # Chỉ lấy mảng xanh sát cánh. Các vùng rời vẫn có thể là lá đài.
        distance = cv2.distanceTransform(cv2.bitwise_not(flower), cv2.DIST_L2, 5)
        # Cuống mảnh có thể hòa vào nền GrabCut. Dò độ tương phản ngang
        # để giữ cuống trên nền xanh và loại vùng nền phẳng cùng màu.
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        bar = np.ones((1, max(7, int(.20 * bw) | 1)), np.uint8)
        contrast = cv2.max(cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, bar),
                           cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, bar))
        plant = cv2.inRange(hsv, (20, 24, 10), (95, 255, 255))
        scontrast = cv2.max(cv2.morphologyEx(hsv[:, :, 1], cv2.MORPH_BLACKHAT, bar),
                           cv2.morphologyEx(hsv[:, :, 1], cv2.MORPH_TOPHAT, bar))
        plant &= cv2.bitwise_or(obj, np.uint8((contrast >= 5) | (scontrast >= 12)) * 255)
        plant = cv2.morphologyEx(plant, cv2.MORPH_CLOSE, kernel)
        plant &= valid
        zone = np.s_[base_y:end, left:right]
        calyx[zone] = plant[zone]
        calyx &= green
        calyx[flower > 0] = 0
        calyx[distance > max(2, .10 * bw)] = 0
        calyx = cv2.morphologyEx(calyx, cv2.MORPH_OPEN, kernel)
        # Đài cần chạm sát cánh và có phần xòe ngang; loại các vệt cuống dọc.
        n, components, stats, _ = cv2.connectedComponentsWithStats(calyx)
        accepted = np.zeros_like(calyx)
        for label in range(1, n):
            _, _, cw, ch, area = stats[label]
            component = components == label
            if (area >= 5 and cw >= .65 * ch and ch <= .22*bw
                    and distance[component].min() <= 2
                    and area <= .25 * cv2.countNonZero(flower)):
                accepted[component] = 255
        calyx = accepted
        # Chỉ bắt đầu từ đoạn gần gốc bông; không nhảy sang một mảng xanh ở xa.
        stem = _attached_stem(plant, flower, bw)
        if not stem.any():
            stem = _edge_stem(img_bgr, flower, valid)
        if not stem.any():
            # Bóng đổ cạnh cuống có thể khiến hai cạnh cùng dấu độ sáng.
            # Thử vài điểm bắt đầu qua vùng giao với đài/lá, giữ đường dài nhất.
            choices=[_edge_stem(img_bgr,flower,valid,int(offset),2,True)
                     for offset in np.linspace(0,.3*bw,6)]
            stem=max(choices,key=lambda m:np.count_nonzero(np.any(m,axis=1)))
        calyx[stem > 0] = 0
    # Kiểm tra cuối chỉ tác động mặt nạ đài, không can thiệp bông/cuống.
    calyx = _validate_calyx(calyx, flower, obj)
    if not calyx.any() and bw and bh:
        # Lá đài nhọn có thể vươn lên hai bên cánh, không chỉ xòe ngang.
        candidate = green & obj & valid
        candidate[flower > 0] = 0
        distance = cv2.distanceTransform(cv2.bitwise_not(flower),cv2.DIST_L2,5)
        yy,xx=np.indices(flower.shape)
        candidate[(yy < y+.55*bh)|(yy > y+bh+.08*bw)|
                  (xx < x-.1*bw)|(xx > x+1.1*bw)|(distance > .1*bw)] = 0
        candidate[stem > 0] = 0
        calyx = _validate_calyx(candidate,flower,obj)
        if cv2.countNonZero(calyx) < max(25,.003*cv2.countNonZero(flower)):
            calyx[:] = 0
    stem_measurement = None
    calyx_attachment = False
    if not calyx.any():
        calyx = calyx_collar(flower,green,obj,valid)
        calyx_attachment = bool(calyx.any())
    if stem.any() and not supported_stem(stem,flower,obj,calyx):
        stem[:] = 0
    if not stem.any() and flower.any():
        stem_measurement = multi_direction_stem(img_bgr, flower, obj, valid, calyx, _edge_stem)
        if stem_measurement is not None:
            stem = stem_measurement['mask']
    if not calyx.any():
        calyx = attachment_calyx(flower, stem, green, obj, valid)
        calyx_attachment = bool(calyx.any())
    calyx[stem > 0] = 0
    if stem_status in ('absent','unobservable'):
        stem[:] = 0
        stem_measurement = None
    if calyx_status in ("absent", "unobservable"):
        calyx[:] = 0
    calyx_reason = (calyx_status if calyx_status in ("absent", "unobservable") else
                    "accepted" if calyx.any() else "unresolved")
    prep = dict(bgr=img_bgr, hsv=hsv, flower_mask=flower, calyx_mask=calyx,
                stem_mask=stem, green_mask=green, obj_mask=obj, valid_mask=valid,
                calyx_status=calyx_status, calyx_reason=calyx_reason,
                stem_measurement=stem_measurement, stem_status=stem_status,
                calyx_attachment=calyx_attachment)
    if use_annotations:
        from organ_annotations import read_annotation,apply_annotation
        prep=apply_annotation(prep,read_annotation(img_bgr),{'calyx':calyx_status,'stem':stem_status})
    return prep
