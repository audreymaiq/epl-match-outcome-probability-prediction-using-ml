# filename: 08_feature_correlation_analysis_v2.py (đặt tên mới để phân biệt)

import pandas as pd
import numpy as np
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN ---
# Thư mục gốc của project (nơi chứa 'preprocessing' và 'data')
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Đường dẫn đến thư mục chứa dữ liệu đã xử lý
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"

# Đường dẫn đến thư mục output của preprocessing để lưu báo cáo tương quan
REPORTS_DIR = BASE_DIR / "preprocessing" / "output"
REPORTS_DIR.mkdir(exist_ok=True) # Tạo thư mục nếu chưa có

# --- THAY ĐỔI 1: Tách biệt Input và Output ---
# Đọc từ file đã có đầy đủ đặc trưng
INPUT_FILENAME = "model_training_dataset.csv" 
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME

# Lưu ra một file mới, không ghi đè
OUTPUT_FILENAME = "final_dataset_for_modeling.csv"
OUTPUT_FILE_PATH = PROCESSED_DATA_DIR / OUTPUT_FILENAME

# File báo cáo các cặp tương quan cao
HIGH_CORR_REPORT_PATH = REPORTS_DIR / "high_correlation_pairs.csv"

# Bạn có thể tăng ngưỡng này nếu muốn giữ lại cặp h2h_btts_rate và h2h_over25_rate
CORRELATION_THRESHOLD = 0.98

def main():
    """
    Hàm chính thực hiện phân tích và loại bỏ các đặc trưng có tương quan cao.
    """
    print("--- TASK 4.3: BẮT ĐẦU PHÂN TÍCH TƯƠNG QUAN GIỮA CÁC ĐẶC TRƯNG ---")

    try:
        df = pd.read_csv(INPUT_FILE_PATH, parse_dates=['Date'])
        print(f"1. Đã đọc thành công file '{INPUT_FILENAME}'.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file '{INPUT_FILE_PATH}'.")
        return

    # Xác định các cột đặc trưng để phân tích
    info_cols = ['Date', 'HomeTeam', 'AwayTeam', 'Season', 'FTR', 'FTHG', 'FTAG']
    feature_cols = [col for col in df.columns if col not in info_cols]
    
    print(f"\n2. Tính toán ma trận tương quan trên {len(feature_cols)} đặc trưng...")
    corr_matrix = df[feature_cols].corr().abs()

    # Tìm các cặp có tương quan cao
    upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    high_corr_pairs = upper_tri[upper_tri > CORRELATION_THRESHOLD].stack().reset_index()
    high_corr_pairs.columns = ['Feature 1', 'Feature 2', 'Correlation']
    
    # Tạo một bản sao để làm việc, giữ nguyên DataFrame gốc
    df_final = df.copy()

    if high_corr_pairs.empty:
        print(f"\n   -> Tốt! Không có cặp đặc trưng nào có tương quan > {CORRELATION_THRESHOLD}")
        print("   -> Không cần loại bỏ cột nào.")
    else:
        print(f"\n3. Tìm thấy {len(high_corr_pairs)} cặp đặc trưng có tương quan > {CORRELATION_THRESHOLD}:")
        print(high_corr_pairs)
        high_corr_pairs.to_csv(HIGH_CORR_REPORT_PATH, index=False)
        print(f"   -> Báo cáo chi tiết đã được lưu tại '{HIGH_CORR_REPORT_PATH}'")

        # Logic để quyết định cột nào sẽ bị loại bỏ
        cols_to_drop = set(high_corr_pairs['Feature 2'])
        
        print(f"\n4. Dựa trên chiến lược đơn giản, quyết định loại bỏ {len(cols_to_drop)} cột sau:")
        print(sorted(list(cols_to_drop)))
        
        # Thực hiện việc loại bỏ trên bản sao
        df_final = df_final.drop(columns=list(cols_to_drop))
        
        print(f"\n   -> DataFrame cuối cùng còn lại {len(df_final.columns)} cột.")
    
    # --- THAY ĐỔI 2 & 3: Lưu vào file mới và cập nhật thông báo ---
    df_final.to_csv(OUTPUT_FILE_PATH, index=False)
    
    print("\n--- HOÀN TẤT TASK 4.3 ---")
    print(f"Bộ dữ liệu cuối cùng, sẵn sàng cho việc huấn luyện mô hình, đã được lưu tại: '{OUTPUT_FILENAME}'")

if __name__ == "__main__":
    main()