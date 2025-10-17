import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

# --- CẤU HÌNH ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Đi lên 3 cấp để đến thư mục gốc của dự án
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports"

# Tự động tạo thư mục reports nếu chưa có
REPORTS_DIR.mkdir(exist_ok=True)

INPUT_FILENAME = "final_cleaned_data.csv"
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME

OUTPUT_REPORT_FILE = REPORTS_DIR / "outlier_report.txt"
OUTPUT_PLOT_DIR = REPORTS_DIR / "outlier_plots"
OUTPUT_PLOT_DIR.mkdir(exist_ok=True)


def detect_outliers_iqr(series):
    """
    Phát hiện outliers trong một Series sử dụng phương pháp IQR.
    Trả về một Series chứa các giá trị outlier.
    """
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    # Tìm các giá trị nằm ngoài ranh giới
    outliers = series[(series < lower_bound) | (series > upper_bound)]
    return outliers

def generate_visualizations(df, numerical_cols, output_dir):
    """
    Tạo và lưu biểu đồ box plot cho các cột số.
    """
    print(f"--- 2. Bắt đầu tạo biểu đồ box plot, lưu tại: '{output_dir}' ---")
    for col in numerical_cols:
        plt.figure(figsize=(10, 4))
        sns.boxplot(x=df[col])
        plt.title(f'Biểu đồ Box Plot cho cột: {col}', fontsize=14)
        
        plot_path = output_dir / f'boxplot_{col}.png'
        plt.savefig(plot_path)
        plt.close() # Đóng biểu đồ để giải phóng bộ nhớ
    print("Hoàn tất tạo biểu đồ.")


def main():
    """
    Hàm chính để chạy toàn bộ quy trình phát hiện outlier.
    """
    print("--- BẮT ĐẦU SCRIPT PHÁT HIỆN OUTLIER ---")
    
    # --- BƯỚC 1: ĐỌC DỮ LIỆU ---
    try:
        df = pd.read_csv(INPUT_FILE_PATH, parse_dates=['Date'])
        print(f"1. Đã đọc thành công file '{INPUT_FILENAME}'.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file '{INPUT_FILE_PATH}'.")
        return

    # Xác định các cột dạng số để phân tích
    numerical_cols = df.select_dtypes(include=np.number).columns.tolist()
    # Loại bỏ các cột không cần phân tích outlier (nếu có)
    if 'Season' in numerical_cols:
        numerical_cols.remove('Season')

    # --- BƯỚC 2: TRỰC QUAN HÓA DỮ LIỆU ---
    generate_visualizations(df, numerical_cols, OUTPUT_PLOT_DIR)

    # --- BƯỚC 3: PHÂN TÍCH THỐNG KÊ VÀ TẠO BÁO CÁO ---
    print(f"--- 3. Bắt đầu phân tích và tạo báo cáo tại: '{OUTPUT_REPORT_FILE}' ---")
    
    with open(OUTPUT_REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("BÁO CÁO PHÂN TÍCH OUTLIER (SỬ DỤNG PHƯƠNG PHÁP IQR)\n")
        f.write("="*50 + "\n\n")

        for col in numerical_cols:
            f.write(f"--- Phân tích cột: {col} ---\n")
            
            outliers = detect_outliers_iqr(df[col])
            
            if outliers.empty:
                f.write("Không phát hiện outlier nào.\n\n")
            else:
                f.write(f"Phát hiện {len(outliers)} outliers.\n")
                f.write(f"Giá trị nhỏ nhất (Min): {df[col].min()}\n")
                f.write(f"Giá trị lớn nhất (Max): {df[col].max()}\n")
                f.write(f"Giá trị outlier nhỏ nhất: {outliers.min()}\n")
                f.write(f"Giá trị outlier lớn nhất: {outliers.max()}\n\n")
                
                f.write("Chi tiết các dòng chứa outlier (để điều tra):\n")
                # Lấy toàn bộ dòng dữ liệu của các outlier để xem ngữ cảnh
                context_df = df.loc[outliers.index]
                f.write(context_df.to_string()) # to_string() để hiển thị đẹp trong file text
                f.write("\n\n" + "-"*50 + "\n\n")

    print("Hoàn tất phân tích.")
    
    # --- BƯỚC 4: HƯỚNG DẪN HÀNH ĐỘNG ---
    print("\n>>> HÀNH ĐỘNG TIẾP THEO <<<")
    print("1. Mở thư mục 'reports/outlier_plots' để xem các biểu đồ box plot.")
    print("2. Mở file 'reports/outlier_report.txt' để xem chi tiết các outlier.")
    print("3. Đối với mỗi outlier được báo cáo, hãy điều tra:")
    print("   - Đó có phải là một trận đấu có thật với tỷ số/thống kê cực đoan không? (VD: Man Utd 9-0 Southampton)")
    print("   - Hay đó là một lỗi nhập liệu? (VD: Tỷ lệ cược < 1.0, số thẻ phạt âm)")
    print("4. Quyết định chiến lược xử lý:")
    print("   - Lỗi dữ liệu: Sửa lại hoặc xóa.")
    print("   - Sự kiện có thật: Giữ nguyên (nếu dùng mô hình cây) hoặc áp dụng phép biến đổi (nếu dùng mô hình tuyến tính).")


if __name__ == "__main__":
    main()