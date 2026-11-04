import os
import streamlit as st
import tempfile
from searcher import search

st.set_page_config(page_title="Tìm kiếm ảnh hoa", layout="wide")
st.title("🌸 Hệ CSDL tìm kiếm ảnh bông hoa")

# --- 1. CHỨC NĂNG UPLOAD ẢNH SO SÁNH ---
st.markdown("---")
st.header("Ảnh đầu vào")

# Khởi tạo file uploader
uploaded_image = st.file_uploader(
    "Chọn ảnh để tải lên", type=["jpg"], accept_multiple_files=False
)
# Khai báo biến lưu đường dẫn tạm ở ngoài để dùng cho phần dưới
temp_path = None

# BẮT BUỘC: Kiểm tra xem người dùng đã upload ảnh chưa
if uploaded_image is not None:
    filename = uploaded_image.name
    st.write("filename: ", filename)

    # Để hiển thị ảnh vừa upload, truyền thẳng đối tượng uploaded_image vào st.image
    st.image(uploaded_image, caption=filename)

    # LƯU FILE VÀO Ổ CỨNG TẠM THỜI ĐỂ LẤY ĐƯỜNG DẪN
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(uploaded_image.getvalue())
        temp_path = tmp.name
else:
    st.info("Vui lòng chọn một bức ảnh để hiển thị.")

# --- 2. CHỨC NĂNG HIỆN THỊ 5 ẢNH TƯƠNG ĐỒNG ---
button = st.button("Tìm kiếm 5 ảnh bông hoa giống nhất")
if button and temp_path is not None:
    st.markdown("---")
    st.header("5 ảnh tương đồng nhất")

    images = []

    with st.spinner("Đang tìm kiếm..."):
        images = search(temp_path, top_k=5)

    cols_per_row = 3  # Số ảnh trên 1 hàng

    # Chia mảng images thành các nhóm nhỏ (mỗi nhóm 3 ảnh)
    for i in range(0, len(images), cols_per_row):
        cols = st.columns(cols_per_row)

        # Lấy 3 ảnh cho vào hàng hiện tại
        chunk = images[i : i + cols_per_row]

        for col, img_path in zip(cols, chunk):
            with col:
                # st.image(img_path, caption=img_path, width=400)
                st.image(img_path, caption=img_path, width="content")

# Tùy chọn: Xóa file tạm sau khi dùng xong để dọn dẹp ổ cứng (nếu muốn)
if temp_path and os.path.exists(temp_path):
    os.remove(temp_path)
