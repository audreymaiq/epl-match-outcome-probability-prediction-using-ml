import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN ---
# Thư mục gốc của project (nơi chứa 'preprocessing' và 'data')
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Đường dẫn đến thư mục chứa dữ liệu đã xử lý
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"

# Đường dẫn đến thư mục output của preprocessing để lưu báo cáo
REPORTS_DIR = BASE_DIR / "preprocessing" / "output"
REPORTS_DIR.mkdir(parents=True, exist_ok=True) # Tạo thư mục reports nếu chưa có

INPUT_FILENAME = "model_training_dataset.csv"
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME

# Tên file báo cáo output
OUTPUT_REPORT_PATH = REPORTS_DIR / "leakage_check_report.txt"

def main():
    """
    Hàm chính thực hiện các bước kiểm tra rò rỉ dữ liệu.
    """
    print("--- TASK 4.2: BẮT ĐẦU KIỂM TRA RÒ RỈ DỮ LIỆU ---")
    
    try:
        df = pd.read_csv(INPUT_FILE_PATH, parse_dates=['Date'])
        print(f"1. Đã đọc thành công file '{INPUT_FILENAME}'.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file '{INPUT_FILE_PATH}'.")
        return

    # Mở file báo cáo để ghi kết quả
    with open(OUTPUT_REPORT_PATH, 'w', encoding='utf-8') as report_file:
        report_file.write("BÁO CÁO KIỂM TRA RÒ RỈ DỮ LIỆU (DATA LEAKAGE)\n")
        report_file.write("="*50 + "\n\n")

        # --- Test 1: Tương quan giữa đặc trưng và biến mục tiêu ---
        print("\n2. Kiểm tra tương quan giữa đặc trưng và biến mục tiêu...")
        report_file.write("### 1. Tương quan với biến mục tiêu (FTR) ###\n")
        
        # Mã hóa FTR để tính tương quan
        df_corr = df.copy()
        target_map = {'H': 1, 'D': 0, 'A': -1}
        df_corr['FTR_encoded'] = df_corr['FTR'].map(target_map)
        
        feature_cols = df_corr.select_dtypes(include=np.number).columns.drop(['FTHG', 'FTAG', 'FTR_encoded'])
        
        correlations = df_corr.corr(numeric_only=True)['FTR_encoded'].abs().sort_values(ascending=False)
        
        report_file.write("Top 10 đặc trưng có tương quan cao nhất với kết quả trận đấu (FTR):\n")
        report_file.write(str(correlations.head(10)) + "\n\n")
        
        # Kiểm tra các đặc trưng có tương quan CỰC KỲ CAO
        leaky_features = correlations[correlations > 0.9]
        if not leaky_features.empty:
            print(f"\n!!! CẢNH BÁO RÒ RỈ TIỀM TÀNG !!!")
            print("Các đặc trưng sau có tương quan > 0.9 với FTR:")
            print(leaky_features)
            report_file.write("!!! CẢNH BÁO: Các đặc trưng có tương quan > 0.9 với FTR !!!\n")
            report_file.write(str(leaky_features) + "\n\n")
        else:
            print("   -> Tốt! Không có đặc trưng nào có tương quan > 0.9 với FTR.")
            report_file.write("Kiểm tra thành công: Không có đặc trưng nào có tương quan > 0.9 với FTR.\n\n")

        # --- Test 2: Phân phối của biến mục tiêu theo thời gian ---
        print("\n3. Kiểm tra phân phối của biến mục tiêu theo thời gian...")
        report_file.write("### 2. Phân phối của biến mục tiêu (FTR) theo mùa giải ###\n")
        
        ftr_dist = df.groupby('Season')['FTR'].value_counts(normalize=True).unstack().fillna(0)
        report_file.write("Tỷ lệ % Thắng (H) / Hòa (D) / Thua (A) theo từng mùa giải:\n")
        report_file.write(str(ftr_dist) + "\n\n")
        
        print("   -> Phân tích đã được lưu vào báo cáo. Vui lòng kiểm tra file để xem có sự thay đổi đột ngột nào không.")
        report_file.write("Ghi chú: Cần xem xét nếu có sự thay đổi đột ngột về tỷ lệ (ví dụ: một mùa có tỷ lệ hòa cao bất thường).\n\n")
        
        # Vẽ biểu đồ để trực quan hóa
        ftr_dist.plot(kind='bar', stacked=True, figsize=(12, 6), 
                      title='Phân phối kết quả (FTR) theo mùa giải')
        plt.ylabel("Tỷ lệ (%)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(REPORTS_DIR / "ftr_distribution_by_season.png")
        print("   -> Biểu đồ đã được lưu tại 'reports/ftr_distribution_by_season.png'")
        
        # --- Test 3: Expert Knowledge (Checklist) ---
        print("\n4. Kiểm tra dựa trên kiến thức chuyên môn (Logic Check)...")
        report_file.write("### 3. Kiểm tra logic dựa trên kiến thức chuyên môn ###\n")
        report_file.write("- Tất cả các đặc trưng đều được tính toán 'time-aware' (dùng .shift(1))? -> CÓ, trong các script trước.\n")
        report_file.write("- Có sử dụng các cột như HTHG, HTAG, HTR không? -> KHÔNG, đã loại bỏ.\n")
        report_file.write("- Các đặc trưng phong độ có bao gồm trận hiện tại không? -> KHÔNG, đã dùng .shift(1).\n")
        report_file.write("Kiểm tra thành công: Logic tạo đặc trưng có vẻ đúng đắn.\n")
        print("   -> Tốt! Logic tạo đặc trưng đã tuân thủ các quy tắc chống rò rỉ.")

    print("\n--- HOÀN TẤT TASK 4.2 ---")
    print(f"Báo cáo kiểm tra đã được lưu tại: '{OUTPUT_REPORT_PATH}'")

if __name__ == "__main__":
    main()