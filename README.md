# BTL_HCSDL DPT - Tìm kiếm ảnh hoa

Ứng dụng trả về 5 ảnh hoa tương đồng nhất với ảnh truy vấn. MySQL lưu thông tin
ảnh và bốn nhóm đặc trưng màu, hình dạng, đài và cuống. Giao diện Streamlit
hiển thị ảnh theo thứ hạng và cho xem phép tính của từng kết quả.

## 1. Yêu cầu môi trường

- Python 3.9 trở lên
- MySQL Server 5.7+ hoặc MySQL 8+
- Git (không bắt buộc, dùng khi clone source)
- Ảnh truy vấn dạng `.jpg` hoặc `.jpeg`, chụp ngang với một bông hoa ở giữa khung hình

## 2. Các thư viện cần thiết

| Thư viện | Mục đích |
|---|---|
| `numpy` | Xử lý mảng và tính toán đặc trưng |
| `opencv-python` | Đọc ảnh, chuyển đổi màu, tạo mask và xử lý ảnh |
| `PyMySQL` | Kết nối và thao tác với MySQL |
| `python-dotenv` | Đọc thông tin cấu hình cơ sở dữ liệu từ file `.env` |
| `streamlit` | Chạy giao diện web tìm kiếm ảnh |

Cài đặt bằng lệnh:

```bash
python -m pip install -r requirements.txt
```

Nếu file `requirements.txt` chưa có nội dung phù hợp, cài trực tiếp:

```bash
python -m pip install numpy opencv-python PyMySQL python-dotenv streamlit
```

## 3. Cấu trúc source chính

```text
.
├── main.py                 # Giao diện Streamlit
├── feature_extractor.py    # Trích xuất 4 nhóm đặc trưng
├── preprocess_image.py     # Tiền xử lý và tạo các mask ảnh
├── save_feature_to_db.py   # Lưu đặc trưng vào MySQL
├── db_connection.py        # Cấu hình và tạo kết nối MySQL
├── db_function.py          # Các hàm đọc dữ liệu từ MySQL
├── searcher.py             # Nhận ảnh truy vấn và trả ảnh tương đồng
├── similarity.py           # Chuẩn hóa và tính khoảng cách của bốn nhóm
├── danh_gia_top5.py        # Tính Precision@5 và đo thời gian truy vấn
├── utils.py                # Hàm tiện ích xử lý ảnh
└── code.sql                # Script tạo database và các bảng
```

## 4. Cài đặt và cấu hình

### Bước 1: Tạo môi trường ảo (khuyến nghị)

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
python -m venv .venv
.\.venv\Scripts\activate.bat
```

### Bước 2: Cài thư viện

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Bước 3: Tạo database

Đăng nhập MySQL và chạy toàn bộ file `code.sql`:

```bash
mysql -u root -p < code.sql
```

Hoặc mở `code.sql` bằng MySQL Workbench và thực thi script. Script sẽ tạo
database `flower_image_db` cùng các bảng:

- `Images`
- `Color_Features`
- `Shape_Features`
- `Calyx_Features`
- `Stem_Features`

### Bước 4: Tạo file `.env`

Tạo file `.env` tại thư mục gốc của project:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=mat_khau_mysql_cua_ban
DB_NAME=flower_image_db
```

Không đưa file `.env` lên Git vì file này chứa thông tin đăng nhập database.

## 5. Chạy ứng dụng

Khởi động giao diện Streamlit:

```powershell
.\.venv\Scripts\python.exe -m streamlit run main.py
```

Sau đó mở địa chỉ được Streamlit hiển thị, thường là:

```text
http://localhost:8501
```

Chọn ảnh và nhấn **Tìm 5 ảnh giống nhất**. Xem **Chi tiết tính điểm Top 5**
để đối chiếu khoảng cách, trọng số và độ phủ của từng kết quả. Mục **Mặt nạ
và 133 giá trị của ảnh truy vấn** cho xem số đo đầu vào.

## 6. Chạy thử các chức năng riêng

### Kiểm tra kết nối MySQL

```bash
python db_connection.py
```

### Nạp kho ảnh và kiểm chứng phần 3

Mặc định chương trình đọc kho `data` ở thư mục cha của dự án. Có thể chỉ định
vị trí khác bằng `--data`. Bốn nhóm đặc trưng được cập nhật trong một giao dịch.

```bash
python save_feature_to_db.py
python kiem_chung_csdl.py
python minh_hoa_phan_3.py
```

Xem [Báo cáo phần 3 · Trích rút và quản trị đặc trưng ảnh bông hoa](bao_cao/phan_3/bao_cao_phan_3.md).

Để lưu riêng một ảnh bằng Python:

```python
from feature_extractor import extract_all_feature
from save_feature_to_db import save_features_to_db

from pathlib import Path

features = extract_all_feature(Path("../data/1.jpg").resolve())
image_id = save_features_to_db(features)
print(image_id)
```

### Đọc dữ liệu từ database

```bash
python db_function.py
```

### Kiểm tra công thức tương đồng (phần 4, bước 4)

Từ thư mục dự án, chạy ví dụ tính điểm một ảnh truy vấn với các ứng viên chỉ định:

```powershell
python minh_hoa_do_tuong_dong.py --query "..\data\7.jpg" --candidates 1.jpg 54.jpg 715.jpg --check
```

### Đánh giá Top 5 trên bộ truy vấn đã chấm

Từ thư mục dự án, dùng môi trường đã cài ở trên và MySQL đã nạp kho ảnh.
Trên máy của nhóm, bộ truy vấn nằm trong `../BTL_TimKiemAnhHoa/BTL_TimKiemAnhHoa/cropped`.
Tham số `--queries` cho phép chỉ định thư mục khác chứa cùng mười tệp.

```powershell
.\.venv\Scripts\python.exe danh_gia_top5.py --repeats 3
```

Xem công thức, ví dụ tính tay, kết quả theo từng truy vấn và phiếu chấm trong [Báo cáo phần 4](bao_cao/phan_4/bao_cao_phan_4.md).

## 7. Lưu ý

### Xác nhận đài tiêu biến và vùng lặp biên

Giao diện có lựa chọn **Tôi xác nhận bông trong ảnh có đài tiêu biến** cho ảnh
truy vấn. Đánh dấu khi nhóm đã có căn cứ xác nhận. Mặc định đài của từng ảnh
được xem là chưa xác nhận và vùng đài được ước lượng từ ảnh.

Để lưu xác nhận cho một ảnh trong MySQL, dùng tên tệp thực tế và ghi căn cứ.
Chương trình lưu trạng thái vào bảng `Image_Review`, cập nhật bốn bộ đặc trưng
của ảnh trong cùng một giao dịch. Ví dụ cú pháp dưới đây dùng tên thay thế.

```powershell
.\.venv\Scripts\python.exe image_review.py --file "TEN_ANH.jpg" --calyx absent --note "Căn cứ xác nhận của nhóm"
```

Các trạng thái được hỗ trợ là `unknown` (chưa xác nhận), `present` (có đài)
và `absent` (đài tiêu biến). Những ảnh chưa được nhóm xác nhận tiếp tục dùng
trạng thái `unknown`.

Chương trình ước lượng dải lặp biên từ các hàng/cột giống nhau liên tiếp sát
mép. Với JPEG, có dung sai sai khác màu. Nền phẳng đơn sắc thiếu bằng chứng
để xác định dải lặp theo cách này. Khi có tọa độ viền từ lần cắt ảnh, hàm
`preprocess_image(..., padding=(top, bottom, left, right))` nhận trực tiếp
độ dày bốn mép theo pixel của ảnh đang đo.

**Loại ảnh trùng và bản cắt cùng nguồn** được bật mặc định trong truy vấn.
Lượt đầu cần đọc ảnh kho và tính các điểm SIFT để kiểm tra cùng nguồn.
Giao diện báo riêng thời gian kiểm tra này và tên các ảnh bị loại.

Đánh giá sau sửa dùng thư mục riêng để đối chiếu với số liệu phiên bản trước.

```powershell
.\.venv\Scripts\python.exe danh_gia_top5.py --out bao_cao/phan_4/danh_gia/sua_phan_vung --repeats 3 --export
```

- `DB_PASSWORD` phải trùng với mật khẩu tài khoản MySQL.
- MySQL phải đang chạy trước khi chạy các chức năng liên quan đến database.
- Kho của nhóm nằm tại `..\data`. Các đường dẫn ảnh trong bảng `Images` phải trỏ tới tệp để giao diện hiển thị được ảnh kết quả.
- Ảnh không đúng định dạng hoặc không đọc được có thể làm bước tiền xử lý
  thất bại.
# Trạng thái quan sát đài hoa

Ở giao diện truy vấn, chọn **Tự động**, **Không xác định được đài trong ảnh**,
**Đã xác nhận đài tiêu biến** hoặc **Tôi xác nhận có đài**. Trạng thái tiêu biến
được so với trạng thái có/tiêu biến đã xác nhận của ảnh trong kho. Không đo được
không đồng nghĩa không có cơ quan đó. Khi chưa rõ trạng thái một bên, không
suy ra một khoản phạt có/không có đài.

Ghi xác nhận cho một ảnh trong kho bằng công cụ có sẵn:

```powershell
.\.venv\Scripts\python.exe -X utf8 image_review.py --file 45.jpg --calyx unobservable --note "Nhóm không xác định được vùng đài trong ảnh"
```

Các giá trị
`--calyx`: `unknown` (trả về tự động), `present` (nhóm xác nhận có đài),
`absent` (nhóm xác nhận tiêu biến), `unobservable` (không xác định được vùng đài).
Xác nhận có đài vẫn cần mặt nạ đạt điều kiện đo. Lệnh chỉ cập nhật ghi chú/xác nhận
và bốn giá trị đài; giữ nguyên các bảng màu, hình dạng, cuống. Kho được nạp lại
theo bộ nhớ đệm tối đa 60 giây; tải lại trang và chạy lại truy vấn sau cập nhật.

## Hiệu chỉnh vùng đài/cuống đã kiểm tra

Trong thanh bên, chọn **Hiệu chỉnh đài/cuống**, chọn ảnh rồi nhấp quanh đường
bao bộ phận và bấm **Khép vùng**. Chọn bộ phận cần hiệu chỉnh và trạng thái;
bấm **Xem trước vùng và số đo**, ghi căn cứ kiểm tra, sau đó mới **Lưu vùng đã
kiểm tra**. Có thể khoanh nhiều vùng rời nhau. Vùng đài/cuống đã vẽ không được
chồng nhau; phần bông và biên lặp ước lượng được loại trong bản xem trước.

Các vùng được lưu ở `annotations/organs/`, gắn với SHA-256 của pixel giải mã,
không gắn bằng tên tệp. Những bản ảnh giống hệt pixel được cập nhật đồng bộ.
Ảnh khác nội dung vẫn dùng bộ dò tự động. Chọn **Giữ tự động** để bỏ hiệu
chỉnh của một bộ phận. Sao lưu thư mục này cùng CSDL nếu chuyển máy.

Lưu hiệu chỉnh chỉ ghi các bảng đài, cuống và `Image_Review`; không ghi bảng
màu/hình dạng. Khi cập nhật trạng thái bằng CLI cho ảnh đã có vùng hiệu chỉnh,
công cụ đồng bộ cả vùng lưu và CSDL. Khi đó hai nhóm đài/cuống có thể cùng được
tính lại do cách xác định vị trí nối của chúng. `--stem` hỗ trợ bốn trạng thái
giống `--calyx`; không được dùng `absent` chỉ vì bộ dò chưa tìm thấy cuống.

Bộ dò tự động vẫn có trường hợp bỏ sót và nhận nhầm. Chức năng hiệu chỉnh
không tự biến các vùng dự đoán thành xác nhận của nhóm.

