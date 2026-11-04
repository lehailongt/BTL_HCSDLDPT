-- 1. Tạo Database
CREATE DATABASE IF NOT EXISTS flower_image_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE flower_image_db;

-- 2. Bảng lưu trữ thông tin cơ bản của ảnh
CREATE TABLE Images (
    image_id INT AUTO_INCREMENT PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,        -- Tên file ảnh (VD: hong_01.jpg)
    file_path VARCHAR(500) NOT NULL,        -- Đường dẫn lưu trữ ảnh
    flower_species VARCHAR(100),            -- Tên loài hoa (nếu biết)
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Bộ thuộc tính 1: Màu sắc chủ đạo
CREATE TABLE Color_Features (
    image_id INT PRIMARY KEY,
    hist_hsv JSON,                          -- Lưu histogram 12H x 3S x 3V dưới dạng JSON (mảng 108 phần tử)
    mean_h FLOAT,                           -- μ_H: Sắc màu trung bình
    mean_s FLOAT,                           -- μ_S: Độ bão hòa trung bình
    std_h FLOAT,                            -- σ_H: Độ lệch chuẩn H
    std_s FLOAT,                            -- σ_S: Độ lệch chuẩn S
    entropy FLOAT,                          -- Entropy histogram
    dominant_color_ratio FLOAT,             -- Tỉ lệ diện tích màu chủ đạo (0-1)
    gradient_s_radius FLOAT,                -- Gradient S theo bán kính
    FOREIGN KEY (image_id) REFERENCES Images(image_id) ON DELETE CASCADE
);

-- 4. Bộ thuộc tính 2: Hình dạng tổng thể
CREATE TABLE Shape_Features (
    image_id INT PRIMARY KEY,
    area FLOAT,                             -- Diện tích bông hoa (tỉ lệ hoặc số pixel)
    perimeter FLOAT,                        -- Chu vi viền
    circularity FLOAT,                      -- Độ tròn C = 4πS/P²
    aspect_ratio FLOAT,                     -- Tỉ lệ khung hình (W/H)
    solidity FLOAT,                         -- Độ đặc (Diện tích mask / Convex hull)
    hu_moment_1 FLOAT,                      -- Hu Moments 1
    hu_moment_2 FLOAT,                      -- Hu Moments 2
    hu_moment_3 FLOAT,                      -- Hu Moments 3
    hu_moment_4 FLOAT,                      -- Hu Moments 4
    hu_moment_5 FLOAT,                      -- Hu Moments 5
    hu_moment_6 FLOAT,                      -- Hu Moments 6
    hu_moment_7 FLOAT,                      -- Hu Moments 7
    FOREIGN KEY (image_id) REFERENCES Images(image_id) ON DELETE CASCADE
);

-- 5. Bộ thuộc tính 3: Đài hoa
CREATE TABLE Calyx_Features (
    image_id INT PRIMARY KEY,
    sepal_length_ratio FLOAT,               -- Tỉ lệ chiều dài lá đài / đường kính bông
    sepal_sharpness FLOAT,                  -- Độ nhọn lá đài (góc đỉnh)
    calyx_adhesion FLOAT,                   -- Mức bao sát (khoảng cách đến cánh / D)
    calyx_area_ratio FLOAT,                 -- Tỉ lệ diện tích đài / diện tích bông
    FOREIGN KEY (image_id) REFERENCES Images(image_id) ON DELETE CASCADE
);

-- 6. Bộ thuộc tính 4: Cuống hoa
CREATE TABLE Stem_Features (
    image_id INT PRIMARY KEY,
    stem_thickness FLOAT,                   -- Độ dày cuống
    stem_width_ratio FLOAT,                 -- Tỉ lệ độ dày cuống / chiều rộng bông
    FOREIGN KEY (image_id) REFERENCES Images(image_id) ON DELETE CASCADE
);


-- Ví dụ: Thêm index cho các trường hay dùng để lọc
CREATE INDEX idx_mean_h ON Color_Features(mean_h);
CREATE INDEX idx_circularity ON Shape_Features(circularity);
CREATE INDEX idx_aspect_ratio ON Shape_Features(aspect_ratio);