"""Dò bộ phận dự phòng theo nhiều hướng; không dùng tên ảnh hay nhãn loài."""
import cv2
import numpy as np


def oriented_views(image, flower, foreground, valid, angles=range(0, 360, 45)):
    h, w = flower.shape
    side = int(np.ceil(np.hypot(h, w)))
    for angle in angles:
        transform = cv2.getRotationMatrix2D((w/2, h/2), angle, 1)
        transform[:, 2] += [(side-w)/2, (side-h)/2]
        def warp(a):
            return cv2.warpAffine(a, transform, (side, side), flags=cv2.INTER_NEAREST)
        yield angle, transform, warp(image), warp(flower), warp(foreground), warp(valid)


def _run_trace(image, flower, foreground, valid, calyx=None):
    """Follow narrow color/foreground components even when edge contrast is weak."""
    x,y,bw,bh = cv2.boundingRect(flower)
    best = np.zeros_like(flower)
    if not bw or not bh:
        return best, 0.
    diameter = max(bw,bh)
    hsv = cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    plant = cv2.inRange(hsv,(28,18,5),(100,255,255))
    # Brown/dark/grey stalks are candidates only in the estimated foreground.
    brown = cv2.inRange(hsv,(0,12,8),(28,255,145))
    neutral = cv2.inRange(hsv,(0,0,8),(179,60,170))
    tissue = plant | brown | neutral
    clean = foreground & valid
    clean[flower>0]=0
    _,labels,_,_=cv2.connectedComponentsWithStats(foreground | flower)
    attached=np.unique(labels[flower>0])
    clean[~np.isin(labels,attached[attached>0])]=0
    distance = cv2.distanceTransform(cv2.bitwise_not(flower),cv2.DIST_L2,5)
    calyx_distance = None
    if calyx is not None and calyx.any():
        calyx_distance = cv2.distanceTransform(cv2.bitwise_not(calyx),cv2.DIST_L2,5)
        cy,cx=np.where(calyx>0);fy,fx=np.where(flower>0)
        calyx_center=np.array([cx.mean(),cy.mean()])
        outward=calyx_center-np.array([fx.mean(),fy.mean()])
    runs_by_row={}
    for row in range(y+round(.6*bh),len(flower)):
        xs=np.flatnonzero(clean[row])
        runs_by_row[row]=[(float(run.mean()),run) for run in np.split(xs,np.flatnonzero(np.diff(xs)>1)+1)
                          if 1<=len(run)<=max(5,.2*diameter)]
    seeds=[]
    for row in range(y+round(.6*bh),min(len(flower),y+bh+max(4,round(.6*diameter)))):
        for mid,run in runs_by_row[row]:
            near=float(distance[row,run].min())
            if x-.15*bw <= mid <= x+1.15*bw and near<.55*diameter:
                seeds.append((near,row,mid))
    used=set();best_score=0.
    for near,start,center in sorted(seeds):
        key=(start//6,int(center)//6)
        if key in used:continue
        used.add(key)
        trace=np.zeros_like(flower);gap=0;last_width=None
        for row in range(start,len(flower)):
            choices=[]
            for mid,run in runs_by_row[row]:
                if abs(mid-center)>max(3,.06*diameter):continue
                if last_width and not max(1,.5*last_width-1)<=len(run)<=max(last_width+2,1.8*last_width):continue
                choices.append((abs(mid-center),mid,run))
            if choices:
                _,center,run=min(choices,key=lambda a:a[0]);trace[row,run]=255;last_width=len(run);gap=0
            else:
                gap+=1
                if gap>2:break
        ys,xs=np.where(trace)
        if not len(xs):continue
        occupied=np.unique(ys).size;length=np.ptp(ys)+1;thickness=len(xs)/occupied
        lastx=int(np.median(xs[ys==ys.max()]))
        boundary=not valid[min(len(valid)-1,int(ys.max())+12),lastx]
        slenderness=1.4 if boundary else 2.5
        if length<max(10,.10*diameter) or length<slenderness*thickness or occupied/length<.85:continue
        if np.mean(tissue[ys,xs]>0)<.65:continue
        # Sepals hug the bloom; a stalk must move away from it.
        distances=distance[ys,xs]
        if np.quantile(distances,.8)<max(7,.16*diameter):continue
        if np.median(distances[ys>=np.quantile(ys,.8)]) <= np.median(distances[ys<=np.quantile(ys,.2)])+max(4,thickness):continue
        if calyx_distance is not None:
            if calyx_distance[ys,xs].min()>max(5,.2*diameter):continue
            direction=np.array([xs.mean(),ys.mean()])-calyx_center
            if np.dot(direction,outward)<.25*np.linalg.norm(direction)*np.linalg.norm(outward):continue
        score=occupied/(1+near/max(4,.08*diameter))
        if score>best_score:best,best_score=trace,score
    return best,best_score


def supported_stem(stem, flower, foreground, calyx=None):
    """Reject fragmented background detections without relabelling them absent."""
    if not stem.any():
        return False
    area=cv2.countNonZero(stem)
    # Intermittent masks are not suitable for measuring stalk thickness.
    connected=cv2.morphologyEx(stem,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    _,_,stats,_=cv2.connectedComponentsWithStats(connected)
    largest=stats[1:,cv2.CC_STAT_AREA].max()
    calyx_near=float('inf')
    if calyx is not None and calyx.any():
        calyx_near=float(cv2.distanceTransform(cv2.bitwise_not(calyx),cv2.DIST_L2,5)[stem>0].min())
    if largest<.7*area and (largest<.4*area or calyx_near>3):
        return False
    dist=cv2.distanceTransform(cv2.bitwise_not(flower),cv2.DIST_L2,5)
    diameter=max(cv2.boundingRect(flower)[2:])
    if min(dist[stem>0].min(),calyx_near)>max(6,.3*diameter):
        return False
    return True


def multi_direction_stem(image, flower, foreground, valid, calyx=None, edge_detector=None):
    best = None
    for angle, transform, im, fl, fg, va in oriented_views(image,flower,foreground,valid):
        ca = cv2.warpAffine(calyx,transform,(len(fl),len(fl)),flags=cv2.INTER_NEAREST) if calyx is not None else None
        mask, score = _run_trace(im,fl,fg,va,ca)
        if not score and edge_detector is not None and ca is not None and ca.any():
            fy,fx=np.where(fl>0);cy,cx=np.where(ca>0)
            outward=np.array([cx.mean()-fx.mean(),cy.mean()-fy.mean()])
            # An edge-only recovery needs a measured calyx and a consistent axis.
            if outward[1]>.7*np.linalg.norm(outward):
                diameter=max(cv2.boundingRect(fl)[2:])
                options=[edge_detector(im,fl,va,int(offset),2,True,float(cx.mean()))
                         for offset in np.linspace(0,.5*diameter,6)]
                candidate=max(options,key=cv2.countNonZero)
                if candidate.any():
                    d=cv2.distanceTransform(cv2.bitwise_not(ca),cv2.DIST_L2,5)
                    near=float(d[candidate>0].min())
                    if near<=max(4,.12*diameter):
                        mask=candidate
                        score=np.count_nonzero(np.any(mask,axis=1))/(1+near/max(4,.08*diameter))
        if score and ca is not None and ca.any():
            fy,fx=np.where(fl>0);cy,cx=np.where(ca>0)
            direction=np.array([cx.mean()-fx.mean(),cy.mean()-fy.mean()])
            if np.linalg.norm(direction)>.05*max(cv2.boundingRect(fl)[2:]):
                score*=max(0,direction[1]/np.linalg.norm(direction))**4
        if score and (best is None or score > best['score']):
            original = cv2.warpAffine(mask,cv2.invertAffineTransform(transform),
                                      (flower.shape[1],flower.shape[0]),flags=cv2.INTER_NEAREST)
            original &= valid
            original[flower > 0] = 0
            # The new path must actually approach the flower attachment. If a
            # calyx has already been measured, use it as the stronger anchor.
            anchor = calyx if calyx is not None and calyx.any() else flower
            dist = cv2.distanceTransform(cv2.bitwise_not(anchor),cv2.DIST_L2,5)
            near = float(dist[original>0].min()) if original.any() else float('inf')
            diameter = max(cv2.boundingRect(flower)[2:])
            if near > max(3,.55*diameter):
                continue
            best = dict(mask=original, measurement_mask=mask, flower_mask=fl,
                        angle=angle, score=float(score))
    return best


def calyx_collar(flower, green, foreground, valid):
    """Find an attached green collar on any side of the bloom."""
    empty=np.zeros_like(flower)
    if not flower.any():return empty
    diameter=max(cv2.boundingRect(flower)[2:])
    distance=cv2.distanceTransform(cv2.bitwise_not(flower),cv2.DIST_L2,5)
    candidate=green & foreground & valid
    candidate[(flower>0)|(distance>.22*diameter)]=0
    n,labels,stats,_=cv2.connectedComponentsWithStats(candidate)
    area=cv2.countNonZero(flower)
    best=None
    for label in range(1,n):
        region=labels==label
        size=stats[label,cv2.CC_STAT_AREA]
        if (max(35,.01*area)<=size<=.3*area
                and np.count_nonzero(distance[region]<=2)>=max(4,.03*diameter)):
            if best is None or size>best[0]:best=(size,region)
    if best is not None:empty[best[1]]=255
    return empty


def attachment_calyx(flower, stem, green, foreground, valid):
    """Estimate calyx around the flower/stem junction, without a fixed up/down rule."""
    empty = np.zeros_like(flower)
    if not stem.any() or not flower.any():
        return empty
    _,_,bw,bh = cv2.boundingRect(flower)
    diameter = max(bw,bh)
    distance = cv2.distanceTransform(cv2.bitwise_not(flower),cv2.DIST_L2,5)
    ys,xs = np.where(stem > 0)
    near = distance[ys,xs] <= distance[ys,xs].min()+max(2,.04*diameter)
    joint = np.array([np.median(xs[near]),np.median(ys[near])])
    # Move from the nearest stem segment to the nearest flower-boundary pixel.
    fy,fx = np.where(flower > 0)
    index = np.argmin((fx-joint[0])**2+(fy-joint[1])**2)
    contact = np.array([fx[index],fy[index]])
    yy,xx = np.indices(flower.shape)
    radius = max(8,.33*diameter)
    candidate = green & foreground & valid
    candidate[(flower > 0)|(stem > 0)|(distance > .18*diameter)|
              ((xx-contact[0])**2+(yy-contact[1])**2 > radius**2)] = 0
    n,labels,stats,_ = cv2.connectedComponentsWithStats(candidate)
    for label in range(1,n):
        region = labels == label
        area = stats[label,cv2.CC_STAT_AREA]
        if (area >= max(12,.002*cv2.countNonZero(flower))
                and np.count_nonzero(distance[region] <= 2) >= 3
                and area <= .3*cv2.countNonZero(flower)):
            empty[region] = 255
    return empty


def shaft_quality(mask):
    """Prefer a coherent shaft over tapering sepals or uneven strips of foliage."""
    widths=np.count_nonzero(mask,axis=1)
    rows=np.flatnonzero(widths)
    if len(rows)<2:return 0.
    widths=widths[rows].astype(float)
    # Robust variation tolerates a short wider junction at the root.
    q10,q90=np.quantile(widths,[.1,.9])
    variation=(q90-q10)/max(1,float(np.median(widths)))
    centers=np.array([np.flatnonzero(mask[row]).mean() for row in rows])
    steps=np.abs(np.diff(centers))
    smoothness=1/(1+float(np.quantile(steps,.9))/max(2,float(np.median(widths))))
    return float(smoothness/(1+variation)**2)


