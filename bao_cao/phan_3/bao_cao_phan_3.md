# Báo cáo phần 3 · Trích rút và quản trị đặc trưng ảnh bông hoa

Nhóm 10 · Hệ CSDL đa phương tiện · Ngày 20/11/2026

**Lần cập nhật phân vùng ngày 21/11/2026** bổ sung loại vùng lặp biên khỏi phép đo, xét thận trọng vùng đài và lần cuống từ gốc bông. Các ví dụ, ảnh và thống kê bên dưới lưu lại lần trích rút ban đầu để đối chiếu. Số liệu của kho sau lần trích lại cùng ảnh mặt nạ mới được ghi trong [phần cập nhật báo cáo phần 4](../phan_4/bao_cao_phan_4.md#sua-phan-vung).

## Bước 1 · Đối chiếu đặc tả trích rút với chương trình và MySQL

Đầu vào là kho ảnh nhóm đã chuẩn bị và kiểm tra tại `D:\ADMIN\Documents\csdlĐPT\data`. Bước này đối chiếu định nghĩa tại Câu 2 của báo cáo đã nộp với ba nơi sử dụng mỗi giá trị: mặt nạ dùng để đo, hàm trích rút và cột lưu trong MySQL.

### Kết quả khảo sát ban đầu

MySQL 8.0.44 đã có CSDL `flower_image_db`. Cả năm bảng dùng InnoDB và mỗi bảng đã có 1.128 dòng. Bảng `Images` có khóa duy nhất trên tên tệp. Bốn bảng con dùng `image_id` làm cả khóa chính và khóa ngoại, có quy tắc xóa liên đới. Bản ghi mẫu của `1.jpg` đang lưu đường dẫn tương đối `data\1.jpg`. Cả 1.128 dòng có nhãn chung `bong hoa`, do đó trường này chưa cung cấp nhãn loài để đánh giá tìm kiếm.

### Bảng đối chiếu

| Đại lượng đã nộp | Hàm và cột đích | Nhận xét trên mã ban đầu |
|---|---|---|
| Histogram HSV, 12 × 3 × 3, tổng 1 | `extract_color_features` → `Color_Features.hist_hsv` | Có đủ 108 ô nhưng chỉ số bị ép tối thiểu bằng 1, làm ô 0 nhập vào ô 1. |
| Trung bình, độ lệch chuẩn của H và S | cùng hàm → `mean_h, mean_s, std_h, std_s` | Đã tính trên vùng bông, H theo độ và S trên thang 0–1. |
| Entropy và tỉ lệ màu chủ đạo | cùng hàm → `entropy, dominant_color_ratio` | Entropy Shannon theo 12 dải H, đơn vị bit. Tỉ lệ lấy theo dải H có nhiều pixel nhất. |
| Gradient S theo bán kính | cùng hàm → `gradient_s_radius` | Hệ số góc của hồi quy S theo khoảng cách đến tâm vùng bông, bán kính đã chia cho giá trị lớn nhất. |
| Diện tích, chu vi, độ tròn | `extract_shape_features` → `Shape_Features.area, perimeter, circularity` | Mã cũ lấy diện tích đa giác và độ dài đường gấp khúc. Báo cáo mô tả đếm pixel vùng và pixel biên. Cần thống nhất phép đo dùng trong cả ba đại lượng. |
| Tỉ lệ rộng/cao, độ đặc | cùng hàm → `aspect_ratio, solidity` | Khung bao đã đúng. Diện tích bông và bao lồi cần đo cùng quy ước pixel. |
| Bảy Hu Moments | cùng hàm → `hu_moment_1…hu_moment_7` | Mã cũ lưu dạng log có dấu. Báo cáo định nghĩa bảy moment, việc chuẩn hóa để so sánh thuộc bước tìm kiếm. |
| Chiều dài lá đài trung bình / đường kính bông | `extract_calyx_features` → `Calyx_Features.sepal_length_ratio` | Mã cũ đo một trục chính của toàn vùng đài. Cần ước lượng từ các đầu lá đài quan sát được rồi lấy trung bình. |
| Góc đỉnh lá đài | cùng hàm → `sepal_sharpness` | Mã cũ lưu 90 trừ góc. Đại lượng đã nộp là góc đỉnh tính bằng độ, góc nhỏ ứng với đầu nhọn. |
| Khoảng cách trung bình từ đài tới cánh gần nhất / D | cùng hàm → `calyx_adhesion` | Mã cũ đặt vùng ngoài bông bằng 0 khi tính biến đổi khoảng cách rồi lấy 1 trừ kết quả. Cần đặt pixel bông làm đích khoảng cách bằng 0 và lưu trực tiếp khoảng cách tương đối. |
| Diện tích đài / diện tích bông | cùng hàm → `calyx_area_ratio` | Dùng số pixel của hai mặt nạ. Mã cũ chặn tỉ lệ ở 1, làm mất giá trị đo khi vùng đài lớn. |
| Độ dày cuống và độ dày / chiều rộng bông | `extract_stem_features` → `Stem_Features.stem_thickness, stem_width_ratio` | Mã đã lấy diện tích chia độ dài quan sát theo hàng ảnh. Chọn vùng xanh lớn nhất ở nửa dưới có thể lấy cả lá và nền. |

### Kiến thức sử dụng và quyết định triển khai

Một đặc trưng nội dung gồm vùng đo, cách đo và đơn vị. Hai cột mang cùng tên chỉ so sánh được khi cả ba điều kiện này thống nhất. Mặt nạ bông ảnh hưởng đồng thời đến màu, hình dạng, đường kính chuẩn hóa đài và chiều rộng chuẩn hóa cuống.

Hệ thống lưu tệp JPEG trên đĩa và quản trị siêu dữ liệu cùng các mô tả nội dung trong CSDL quan hệ. Khi nạp lại, chương trình cần nhận ra ảnh qua tên tệp, giữ liên kết bằng `image_id` và cập nhật nhất quán cả bốn nhóm. Bước 2 xử lý các sai lệch phép đo; bước 3 cập nhật đường dẫn về kho đã chỉ định và kiểm chứng bằng truy vấn trên dữ liệu đã lưu.

## Bước 2 · Trích rút bốn bộ đặc trưng trên ảnh hoa

Ảnh chuẩn đi vào `preprocess_image.py` dưới dạng ma trận BGR. Chương trình tạo ba mặt nạ nhị phân có cùng kích thước với ảnh. Sau đó `feature_extractor.py` đo 115 giá trị màu, 12 giá trị hình dạng, 4 giá trị đài và 2 giá trị cuống. Mỗi ảnh có 133 giá trị số. Màu chứa 108 ô histogram và 7 đại lượng vô hướng.

### Cách xác định vùng đo

1. GrabCut khởi tạo bằng hình chữ nhật gần mép ảnh và ước lượng vùng tiền cảnh. Chương trình chuyển sang HSV, loại vùng xanh lá và vùng rất tối khỏi vùng cánh, mở hình thái bằng nhân 3 × 3 để giảm đốm nhiễu. Điểm chọn thành phần liên thông ưu tiên vùng lớn gần tâm. Khi vùng bông quá nhỏ, chương trình thử vùng có màu bão hòa gần tâm.
2. Chương trình tìm vùng đài quanh phần dưới của bông. Vị trí, giới hạn khoảng cách đến cánh, dải màu xanh đến vàng xanh và tương phản ngang giúp thu hẹp vùng đo khi nền cũng màu xanh. Các quy tắc dựa trên tư thế chụp ngang trong kho ảnh.
3. Từ phía dưới bông và đài, chương trình lần theo các đoạn xanh hẹp ở các hàng liên tiếp để đo cuống. Điều kiện bề rộng và độ dịch ngang hạn chế việc lần sang lá bên cạnh. Các mặt nạ và tham số phân đoạn là dữ liệu trung gian.

### Giá trị và đơn vị

| Nhóm | Phép đo |
|---|---|
| Màu | Histogram lấy trên pixel bông, chỉ số ô bằng `9h + 3s + v`, chuẩn hóa theo số pixel. Trung bình và độ lệch chuẩn của H dùng độ, của S dùng thang 0–1. Entropy bằng −Σp log₂p trên 12 dải H, tỉ lệ màu chủ đạo bằng max(p). Gradient là hệ số góc của S theo bán kính đã chia cho bán kính lớn nhất. |
| Hình dạng | Đếm pixel bông A và lưu `A/(rộng ảnh × cao ảnh)`. P là số điểm trên đường biên ngoài 8-liên thông. Độ tròn bằng `4πA/P²`. Tỉ lệ khung bao bằng rộng/cao. Độ đặc bằng A chia số pixel bao lồi đã tô kín. Bảy Hu Moments tính trực tiếp từ moment của mặt nạ nhị phân. |
| Đài | D là cạnh dài của khung bao bông. Gốc lá đài được ước lượng ở chỗ nối cuống. Trên đường biên đã xấp xỉ bằng đa giác, các đỉnh có bán kính đạt cực đại cục bộ và góc dưới 150° là ứng viên đầu lá. Lấy trung bình chiều dài gốc–đỉnh rồi chia D, và trung bình góc tại những đỉnh đó theo độ. Mức bao sát bằng khoảng cách Euclid trung bình từ pixel đài tới pixel cánh gần nhất chia D. Giá trị nhỏ ứng với đài sát cánh. Tỉ lệ diện tích lấy từ số pixel hai mặt nạ. |
| Cuống | Độ dày bằng số pixel cuống chia độ dài quan sát theo phương dọc (pixel). Chia độ dày cho chiều rộng khung bao bông để có tỉ lệ tương đối. |

H trung bình là trung bình số học theo đặc tả; các pixel đỏ ở hai phía của mốc 0°/360° có thể làm giá trị này khó diễn giải. Khi đó cần đọc cùng histogram. Do P đếm điểm biên trên lưới pixel, độ tròn rời rạc có thể lớn hơn 1. Chiều dài và góc lá đài là ước lượng hai chiều từ phần quan sát được. Cuống nghiêng mạnh cũng ảnh hưởng phép đo chiều dài dọc.

### Minh họa từ kho ảnh

Từ trái sang phải là ảnh gốc, ảnh chồng màu, mặt nạ bông, mặt nạ đài và mặt nạ cuống. Trên ảnh chồng màu, tím biểu thị bông, vàng cam biểu thị đài và xanh lam biểu thị cuống.

![Năm ảnh mẫu và vùng thực tế dùng để đo](minh_hoa/mat_na.png)

| Ảnh | H trung bình (°) | S trung bình | Diện tích bông / ảnh | Khoảng cách đài–cánh / D | Diện tích đài / bông | Độ dày cuống (px) |
|---|---:|---:|---:|---:|---:|---:|
| 7.jpg | 276,91 | 0,6349 | 0,2676 | 0,0285 | 0,0912 | 11,36 |
| 54.jpg | 215,34 | 0,3525 | 0,3269 | 0,0349 | 0,1178 | 0 |
| 495.jpg | 59,77 | 0,1588 | 0,1947 | 0,0348 | 0,0977 | 0 |
| 715.jpg | 136,42 | 0,0922 | 0,2653 | 0,0318 | 0,0083 | 10,91 |
| 803.jpg | 38,73 | 0,9293 | 0,1099 | 0,0321 | 0,1250 | 0 |

Ảnh 7 và 715 cho thấy thuật toán theo được cuống ở dưới bông. Ở ảnh 495, lá sát cuống đi vào vùng ước lượng đài. Ở ảnh 803, cuống lệch sang phải và chương trình bỏ sót. Giá trị cuống bằng 0 là quy ước *chưa đo được*. Tương tự, bốn số 0 của nhóm đài báo hiệu chưa thu được vùng đài đủ lớn. Khi có vùng đài nhưng thiếu đỉnh hợp lệ, chỉ chiều dài và góc nhận giá trị 0. Các mặt nạ mẫu cho phép phân biệt thiếu quan sát với việc bộ phận thực sự tiêu giảm.

### Kiểm chứng và tái lập

Trong bộ slide của môn, Lecture 11, trang PDF 4–5 mô tả luồng phân đoạn và trích đặc trưng ngoại tuyến, trang 13 giải thích lượng tử hóa và histogram, trang 27–31 trình bày mô tả hình dạng cùng bảy Hu Moments. Nhóm cụ thể hóa các nguyên lý này bằng không gian HSV và quy ước đo đài, cuống đã trình bày ở Câu 2.

- Histogram hai pixel đặt ở hai đầu không gian màu cho 0,5 tại ô 0 và 107. Cả năm histogram mẫu có 108 ô, sai số tổng so với 1 nhỏ hơn 0,000001.
- Mặt nạ chữ nhật 40 × 20 trên ảnh 80 × 80 cho diện tích tương đối 0,125, chu vi 116 điểm biên và độ đặc 1. Cuống rộng 4 pixel cho độ dày 4 và tỉ lệ 0,1.
- Đài tam giác có chiều cao 10 pixel và đường kính bông 40 pixel cho tỉ lệ chiều dài 0,25 và góc đỉnh 53,13°. Dịch đài xuống 8 pixel làm mức khoảng cách tăng từ 0,2137 lên 0,4137, đúng bằng 8/40.

Từ thư mục dự án chạy `.\.venv\Scripts\python.exe -m unittest -v test_phan_3` để lặp lại ba phép kiểm hình học và histogram. Chạy `.\.venv\Scripts\python.exe minh_hoa_phan_3.py` để tái tạo hình và [toàn bộ giá trị mẫu](minh_hoa/dac_trung.json). Phép kiểm bằng hình học kiểm tra công thức. Việc quan sát ảnh chồng màu kiểm tra chất lượng phân vùng.

## Bước 3 · Nạp và nghiệm thu CSDL đặc trưng ảnh hoa

Đã cập nhật CSDL quan hệ `flower_image_db` trên MySQL 8.0.44 bằng kết quả trích rút từ `D:\ADMIN\Documents\csdlĐPT\data`. Sau khi giao dịch hoàn tất, chương trình kiểm chứng mở một kết nối mới và đọc lại đủ bốn nhóm của cả 1.128 ảnh.

### Thiết kế và kiến thức sử dụng

| Bảng | Dữ liệu quản trị | Khóa |
|---|---|---|
| Images | Tên tệp, đường dẫn tuyệt đối, nhãn nếu có, thời điểm thêm | PK `image_id`, UNIQUE `file_name` |
| Color_Features | Histogram HSV trong một mảng JSON, bảy đại lượng số dạng FLOAT | PK và FK `image_id` |
| Shape_Features | Diện tích tương đối, chu vi, độ tròn, tỉ lệ khung, độ đặc và bảy Hu Moments | PK và FK `image_id` |
| Calyx_Features | Tỉ lệ chiều dài lá đài, góc đỉnh, khoảng cách tương đối tới cánh và tỉ lệ diện tích | PK và FK `image_id` |
| Stem_Features | Độ dày cuống và tỉ lệ độ dày/chiều rộng bông | PK và FK `image_id` |

Tệp JPEG nằm trên ổ đĩa. Đường dẫn trong bảng ảnh cho phép mở tệp gốc, còn các bảng con cho phép truy vấn số đo bằng SQL. Khóa ngoại bảo đảm mỗi dòng đặc trưng thuộc về một ảnh có thật. Khóa chính trên cùng cột giới hạn mỗi nhóm ở một dòng cho mỗi ảnh. Phép JOIN cả bốn bảng mới chứng minh được một ảnh có đủ bốn dòng. Thiết kế vận dụng mô hình quan hệ ở Lecture 5, trang PDF 6–9 và sự phân biệt giữa thông tin mô tả với đặc trưng nội dung ở Lecture 9, trang PDF 22–25.

### Quy trình ghi

1. Đọc lần lượt ảnh trong kho, tính các giá trị bằng cùng bộ trích rút đã dùng ở bước 2. Các mô tả số được giữ trong bộ nhớ cho tới khi xử lý xong danh sách ảnh.
2. Mở giao dịch InnoDB. Tìm lại dòng ảnh thông qua khóa duy nhất `file_name`. Khi trùng tên, cập nhật đường dẫn và lấy lại `image_id` hiện có. Khi chưa có tên, tạo dòng mới. Tên tệp là định danh nghiệp vụ trong phạm vi kho ảnh phẳng của nhóm.
3. Dùng cùng `image_id` để thêm hoặc cập nhật cả bốn bảng con. Bộ ghi kiểm tra histogram dài 108, không âm, tổng gần 1, có đủ bảy Hu Moments và các đại lượng số hữu hạn.
4. COMMIT sau khi toàn bộ lần ghi thành công. Khi một lệnh ghi phát sinh lỗi, ROLLBACK cả lượt ghi để các ảnh trong kho sử dụng cùng phiên bản phép đo.

Đã đối chiếu trước và sau giao dịch trên toàn bộ các bộ giá trị `(image_id, file_name, flower_species, upload_date)` theo thứ tự khóa chính. Hai tập cho cùng kết quả băm SHA-256. Nhãn cũ `bong hoa` là nhãn chung của kho.

### Kết quả đọc lại

| Phép kiểm | Kết quả |
|---|---:|
| Dòng ở Images / Color_Features / Shape_Features / Calyx_Features / Stem_Features | 1.128 / 1.128 / 1.128 / 1.128 / 1.128 |
| Ảnh khớp tên, đường dẫn trong kho chỉ định và đủ bốn nhóm qua JOIN | 1.128 |
| Histogram có 108 ô không âm, tổng gần 1 | 1.128 |
| Sai số tuyệt đối lớn nhất của tổng histogram so với 1 | 4,1 × 10⁻⁸ |
| Ảnh có NULL hoặc giá trị số không hữu hạn trong các dòng đặc trưng đọc lại | 0 |
| Ảnh chưa đo được vùng đài | 17 |
| Ảnh có vùng đài nhưng thiếu đỉnh hợp lệ để ước lượng chiều dài và góc | 2 |
| Ảnh chưa đo được cuống | 243 |
| Ảnh mẫu được trích lại độc lập và so sánh đủ 133 số với MySQL | 5/5 |

Năm ảnh dùng để đối chiếu là `7.jpg`, `54.jpg`, `495.jpg`, `715.jpg` và `803.jpg`. Phép so sánh có dung sai để tính đến độ chính xác của cột FLOAT. Ví dụ, với `image_id=7`, MySQL trả `mean_s=0.634854`, `area=0.267639`, `calyx_adhesion=0.0284953` và `stem_thickness=11.3636`. Trước khi cập nhật, cùng ảnh có diện tích tương đối 0,992203 và độ dày cuống 152,539 pixel. Có thể đối chiếu hai đại lượng mới với vùng bông và vùng cuống ở hàng đầu của [hình minh họa](minh_hoa/mat_na.png).

Các thống kê đài và cuống phản ánh **khả năng thu được số đo**. Để xác định độ chính xác phân vùng cần mặt nạ tham chiếu do người đánh dấu. Khi sử dụng dữ liệu ở phần tìm kiếm, cần xét quy ước thiếu quan sát của bước 2 trước khi so sánh hai giá trị bằng 0.

### Lệnh tái lập

Chạy từ thư mục `BTL_HCSDLDPT` khi MySQL đã mở. Lệnh thứ nhất tính lại và cập nhật các dòng đặc trưng. Lệnh thứ hai chỉ đọc để nghiệm thu.

```powershell
.\.venv\Scripts\python.exe save_feature_to_db.py --data 'D:\ADMIN\Documents\csdlĐPT\data'
.\.venv\Scripts\python.exe kiem_chung_csdl.py --data 'D:\ADMIN\Documents\csdlĐPT\data'
```

Truy vấn sau dùng để trình bày đường đi từ ảnh gốc đến bốn nhóm đặc trưng trên MySQL:

```sql
SELECT i.image_id, i.file_name, i.file_path,
       JSON_LENGTH(c.hist_hsv) AS so_o_hsv, c.mean_s,
       sh.area, ca.calyx_adhesion, st.stem_thickness
FROM Images AS i
JOIN Color_Features AS c  USING (image_id)
JOIN Shape_Features AS sh USING (image_id)
JOIN Calyx_Features AS ca USING (image_id)
JOIN Stem_Features AS st  USING (image_id)
WHERE i.image_id = 7;
```
