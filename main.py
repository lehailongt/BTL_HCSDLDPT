from math import isnan
from pathlib import Path

import cv2
import streamlit as st
from pymysql import MySQLError

from searcher import FlowerCatalog, decode_query, search_image
from similarity import FIELDS, GROUPS


GROUP_NAMES = {"color": "Màu", "shape": "Hình dạng", "calyx": "Đài", "stem": "Cuống"}
CALYX_OPTIONS = {"Tự động": "unknown", "Không xác định được đài trong ảnh": "unobservable",
                 "Đã xác nhận đài tiêu biến": "absent", "Tôi xác nhận có đài": "present"}
STEM_OPTIONS = {"Tự động": "unknown", "Tôi xác nhận có cuống": "present",
                "Tôi xác nhận ảnh không có cuống": "absent", "Cuống bị che hoặc không quan sát được": "unobservable"}


@st.cache_resource(ttl=60, show_spinner=False)
def gallery():
    # Hiệu chỉnh khoảng cách nhóm và thống kê H vòng tròn.
    return FlowerCatalog.load()


def clear_result():
    st.session_state.pop("flower_result", None)
    st.session_state.pop("detail_rank", None)


def change_upload():
    clear_result()
    st.session_state["calyx_choice"] = "Tự động"
    st.session_state["stem_choice"] = "Tự động"


def show_query_features(result):
    with st.expander("Mặt nạ và 133 giá trị của ảnh truy vấn"):
        if result.get("calyx_status") == "absent":
            st.info("Đài tiêu biến theo xác nhận. Trạng thái này được so với ảnh có trạng thái "
                    "đài đã xác nhận; không suy ra tiêu biến từ việc chưa đo được.")
        elif result.get("calyx_reason") in ("unobservable", "unresolved"):
            st.info("Chưa xác định được vùng đài để đo. Nhóm đài không tham gia tính điểm; "
                    "điều này không xác nhận đài tiêu biến.")
        valid = result["masks"].get("valid_mask")
        if valid is not None:
            ignored = valid.size - cv2.countNonZero(valid)
            st.caption(f"Vùng biên lặp ước lượng đã loại khỏi phép đo · {ignored:,} pixel")
        cols = st.columns(3)
        for col, (key, title) in zip(cols, (("flower_mask", "Bông"), ("calyx_mask", "Đài"),
                                           ("stem_mask", "Cuống"))):
            mask = result["masks"][key]
            col.image(mask, caption=f"{title} · {cv2.countNonZero(mask):,} pixel", width=180)
        descriptor = result["descriptor"]
        st.caption('Đài: '+descriptor.organ_state('calyx')+' · Cuống: '+descriptor.organ_state('stem'))
        rows = []
        for group, indexes in GROUPS.items():
            for i in indexes:
                x = descriptor.values[i]
                unavailable = "Chưa đo được"
                if group in ('calyx','stem') and getattr(descriptor,group+'_status')=='absent':
                    unavailable = 'Không áp dụng — không có (đã xác nhận)'
                rows.append({"Nhóm": GROUP_NAMES[group], "Thuộc tính": FIELDS[i],
                             "Giá trị đo": unavailable if isnan(x) else f"{x:.8g}"})
        st.dataframe(rows, hide_index=True)
        st.caption("Histogram HSV · 12 dải H × 3 dải S × 3 dải V, tổng bằng 1.")
        bins = descriptor.hist.reshape(12, 3, 3)
        st.dataframe([{"H (độ)": f"{h*30}–{(h+1)*30}",
                       **{f"S{s} V{v}": float(bins[h,s,v]) for s in range(3) for v in range(3)}}
                      for h in range(12)], hide_index=True)


def show_matches(result):
    hits = result["matches"]
    excluded = result.get("excluded_sources", [])
    if excluded:
        st.info(f"Đã loại {len(excluded)} ảnh trùng hoặc khớp cùng nguồn với truy vấn · "
                + ", ".join(excluded))
    st.caption(f"Kiểm tra ảnh cùng nguồn {result.get('source_filter_ms', 0):.0f} ms")
    if not hits:
        st.warning("Kho chưa còn ảnh khác nguồn để hiển thị.")
        show_query_features(result)
        return
    st.subheader(f"{len(hits)} ảnh tương đồng nhất")
    st.caption(f"Đã so với {result['compared']:,} ảnh · Trích đặc trưng {result['extract_ms']:.0f} ms"
               f" · Tính điểm và xếp hạng {result['rank_ms']:.0f} ms")
    for rank, (col, hit) in enumerate(zip(st.columns(len(hits)), hits), 1):
        col.markdown(f"**#{rank} · {hit['file_name']}**")
        path = Path(hit["file_path"])
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        if path.is_file():
            col.image(str(path), width="stretch")
        else:
            col.warning("Chưa tìm thấy tệp ảnh theo đường dẫn trong CSDL.")
        col.markdown(f"**S = {hit['similarity']:.4f}**")
        col.caption(f"Độ phủ {hit['coverage']:.0%}")
    with st.expander("Chi tiết tính điểm Top 5"):
        rows = []
        for rank, hit in enumerate(hits, 1):
            row = {"Hạng": rank, "Ảnh": hit["file_name"]}
            for organ,label in (('calyx','Đài'),('stem','Cuống')):
                row['Trạng thái '+label.lower()] = hit.get('organ_states',{}).get(organ,'Chưa xác định')
            for group, name in GROUP_NAMES.items():
                d = hit["distances"][group]
                row[f"D · {name}"] = hit.get("missing_reason",{}).get(group,"Chưa đo được") if d is None else f"{d:.6f}"
            rows.append({**row, "D tổng": f"{hit['total_distance']:.6f}",
                         "S": f"{hit['similarity']:.6f}", "Độ phủ": f"{hit['coverage']:.0%}"})
        st.dataframe(rows, hide_index=True)
        rank = st.selectbox("Xem trọng số và đóng góp của từng nhóm", range(1, len(hits)+1),
                            format_func=lambda k: f"Hạng {k} · {hits[k-1]['file_name']}",
                            key="detail_rank")
        hit = hits[rank-1]
        parts = []
        for group, name in GROUP_NAMES.items():
            w, d = hit["weights"][group], hit["distances"][group]
            parts.append({"Nhóm": name, "Khoảng cách Dg": hit.get("missing_reason",{}).get(group,"Chưa đo được") if d is None else f"{d:.6f}",
                          "D trước hiệu chỉnh": (f"{hit['raw_distances'][group]:.6f}"
                                                 if hit.get('raw_distances',{}).get(group) is not None else "—"),
                          "Hệ số chia": f"{hit.get('group_factors',{}).get(group,1):.6f}",
                          "Trọng số thực": f"{w:.2%}",
                          "Đóng góp vào D": f"{w*d:.6f}" if d is not None else "0"})
        st.dataframe(parts, hide_index=True)
        if hit.get('calyx_state_comparison'):
            st.caption("Nhóm đài đang so trạng thái có/tiêu biến đã được xác nhận.")
        if hit.get('organ_state_comparisons',{}).get('stem'):
            st.caption("Nhóm cuống đang so trạng thái có/không có đã được xác nhận ở cả hai ảnh.")
        st.caption(f"Khoảng cách histogram kết hợp HSV/HS = {hit['hist_distance']:.6f} · "
                   f"S = 1 / (1 + {hit['total_distance']:.6f}) = {hit['similarity']:.6f}")
    show_query_features(result)


def main():
    st.set_page_config(page_title="Tìm ảnh hoa tương đồng", layout="wide")
    if st.session_state.get("result_version") != 10:
        clear_result()
        gallery.clear()
        st.session_state["result_version"] = 10
    mode=st.sidebar.radio('Chức năng',['Tìm ảnh tương đồng','Hiệu chỉnh đài/cuống'])
    if mode=='Hiệu chỉnh đài/cuống':
        from organ_review_ui import review_screen
        def refreshed():
            gallery.clear()
            clear_result()
        review_screen(gallery(),refreshed)
        return
    st.title("Tìm ảnh hoa tương đồng")
    entry, preview = st.columns([3, 1])
    with entry:
        upload = st.file_uploader("Ảnh truy vấn", type=["jpg", "jpeg"], key="flower_upload",
                                  on_change=change_upload,
                                  help="Chọn ảnh có một bông ở giữa khung hình, nhìn ngang.")
        if upload is None:
            st.button("Tìm 5 ảnh giống nhất", disabled=True)
            return
        try:
            image, (width, height) = decode_query(upload.getvalue())
        except (ValueError, cv2.error) as exc:
            st.error(f"Không thể dùng ảnh truy vấn. {exc}")
            return
        preview.image(image, channels="BGR", width=180,
                      caption=f"Ảnh truy vấn · {width} × {height} → 256 × 256")
        calyx_choice = st.selectbox("Quan sát đài hoa", list(CALYX_OPTIONS),
                                   key="calyx_choice", on_change=clear_result)
        stem_choice = st.selectbox("Quan sát cuống hoa",list(STEM_OPTIONS),
                                  key='stem_choice',on_change=clear_result)
        exclude_sources = st.checkbox("Loại ảnh trùng và bản cắt cùng nguồn", value=True,
                                       key="exclude_sources", on_change=clear_result)
        clicked = st.button("Tìm 5 ảnh giống nhất", type="primary")
    if clicked:
        clear_result()
        try:
            with st.spinner("Đang so sánh với kho ảnh…"):
                st.session_state.flower_result = search_image(
                    image, upload.name, gallery(),
                    calyx_status=CALYX_OPTIONS[calyx_choice],
                    exclude_same_source=exclude_sources,stem_status=STEM_OPTIONS[stem_choice])
        except (RuntimeError, ValueError, OSError, MySQLError, cv2.error) as exc:
            st.error(f"Chưa hoàn tất truy vấn. {exc}")
    if "flower_result" in st.session_state:
        show_matches(st.session_state.flower_result)


if __name__ == "__main__":
    main()
