import pandas as pd
from pathlib import Path

# --- ĐỊNH NGHĨA CHIẾN LƯỢC ---
# Đây là phần "bộ não" quyết định cột nào và dòng nào sẽ bị xử lý.
CLEANING_STRATEGY = {
    # 1. DANH SÁCH CÁC CỘT CẦN LOẠI BỎ
    "columns_to_drop": {
        "reason_unstable_bookies": [
             # Các nhà cái không ổn định
            'BW*', 'WH*', 'IW*', 'SJ*', 'VC*', 'LB*', 'GB*', 'BS*'
        ],
        "reason_new_bookies": [
            # Các nhà cái mới xuất hiện gần đây
            '1XB*', 'BF*'
        ],
        "reason_redundant_or_recreatable": [
            # Các cột có thể tái tạo từ các cột khác hoặc không cần thiết
            # Và không biết được tính toán dựa trên nhà cái nào
            'Bb*', 'Avg*', 'Max*'
        ],
        "reason_low_value_or_inconsistent": [
            # Các cột có giá trị thấp hoặc không nhất quán
            'Referee', 'Time', 'Div'
        ],
        "reason_data_leakage_for_prematch_model": [
             # Bỏ vì dự đoán TRƯỚC trận đấu
            'HTHG', 'HTAG', 'HTR'
        ],
        "reason_not_consistent_across_all_seasons": [
            # Các loại kèo chỉ xuất hiện ở các mùa gần đây
            'B365<2.5', 'B365>2.5', 'B365AHA', 'B365AHH', 'B365C<2.5', 'B365C>2.5', 
            'B365CA', 'B365CAHA', 'B365CAHH', 'B365CD', 'B365CH', 'P<2.5', 'P>2.5', 
            'PAHA', 'PAHH', 'PC<2.5', 'PC>2.5', 'PCAHA', 'PCAHH', 'AHCh', 'AHh'
        ]
    },

    # 2. CÁCH XỬ LÝ CÁC DÒNG BỊ LỖI
    "row_handling": {
        # Xóa bất kỳ dòng nào có giá trị thiếu trong các cột CỐT LÕI này
        "dropna_on_critical_columns": [
            'FTHG', 'FTAG', 'FTR', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 
            'B365A', 'PSCH', 'PSCD', 'PSCA'
        ]
    }
}

# --- CẤU HÌNH ĐƯỜNG DẪN ---
try:
    # Bắt đầu từ vị trí của file script này
    SCRIPT_DIR = Path(__file__).resolve().parent
    # Đi ngược lên 2 cấp để đến thư mục gốc của dự án (thư mục chứa 'preprocessing' và 'data')
    # processing_data -> preprocessing -> project_root
    PROJECT_ROOT = SCRIPT_DIR.parent.parent
    # Bây giờ, từ thư mục gốc, đi xuống thư mục data/processed một cách chính xác
    PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
except NameError:
    # Fallback trong trường hợp chạy trên môi trường không có __file__ (ví dụ Jupyter)
    PROJECT_ROOT = Path.cwd()
    PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

# Đọc file đã được chuẩn hóa tên đội và ngày tháng
INPUT_FILENAME = "combined_seasons.csv" 
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME
# Tên file output cuối cùng
OUTPUT_FILENAME = "final_cleaned_data.csv" # file này đã loại boc các cột không cần thiết
OUTPUT_FILE_PATH = PROCESSED_DATA_DIR / OUTPUT_FILENAME



def apply_cleaning_strategy(df, strategy):
    """
    Áp dụng chiến lược làm sạch được định nghĩa vào DataFrame.
    """
    print("--- 2. Bắt đầu áp dụng chiến lược làm sạch ---")
    
    # --- XỬ LÝ CỘT ---
    initial_cols = set(df.columns)
    # Lấy tất cả các pattern từ dictionary chiến lược
    cols_to_drop_patterns = [p for reason in strategy["columns_to_drop"].values() for p in reason]
    
    actual_cols_to_drop = set()
    for col in df.columns:
        for pattern in cols_to_drop_patterns:
            # Xử lý các pattern có dấu '*' (wildcard)
            if pattern.endswith('*') and col.startswith(pattern[:-1]):
                actual_cols_to_drop.add(col)
            # Xử lý các tên cột chính xác
            elif col == pattern:
                actual_cols_to_drop.add(col)
    
    df_cleaned = df.drop(columns=list(actual_cols_to_drop), errors='ignore')
    print(f"2.1. Đã loại bỏ {len(initial_cols) - len(df_cleaned.columns)} cột.")

    # --- XỬ LÝ DÒNG ---
    critical_cols = strategy["row_handling"]["dropna_on_critical_columns"]
    # Đảm bảo chỉ xóa trên các cột thực sự tồn tại trong DataFrame sau khi đã bỏ bớt cột
    critical_cols_exist = [col for col in critical_cols if col in df_cleaned.columns]
    
    rows_before_drop = len(df_cleaned)
    df_cleaned = df_cleaned.dropna(subset=critical_cols_exist)
    rows_after_drop = len(df_cleaned)
    print(f"2.2. Đã loại bỏ {rows_before_drop - rows_after_drop} dòng có giá trị thiếu ở các cột cốt lõi.")
    
    return df_cleaned

def main():
    """
    Hàm chính để chạy toàn bộ quy trình.
    """
    print("--- BẮT ĐẦU SCRIPT THANH LỌC DỮ LIỆU ---")
    
    # --- BƯỚC 1: ĐỌC DỮ LIỆU ---
    try:
        # Giả định file combined_seasons.csv đã được chuẩn hóa tên đội và cột Date
        df = pd.read_csv(INPUT_FILE_PATH, parse_dates=['Date'])
        print(f"1. Đã đọc thành công file '{INPUT_FILENAME}' với {len(df)} dòng và {len(df.columns)} cột.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file tại đường dẫn '{INPUT_FILE_PATH}'.")
        print("Vui lòng kiểm tra lại cấu trúc thư mục và logic xác định đường dẫn trong script.")
        return

    # --- BƯỚC 2: ÁP DỤNG CHIẾN LƯỢC ---
    final_df = apply_cleaning_strategy(df, CLEANING_STRATEGY)

    # --- BƯỚC 3: KIỂM TRA VÀ LƯU OUTPUT ---
    print("\n--- 3. Hoàn tất và lưu kết quả ---")
    print(f"DataFrame cuối cùng có {len(final_df)} dòng và {len(final_df.columns)} cột.")
    print("Các cột được giữ lại:")
    print(sorted(final_df.columns.tolist()))
    
    # Kiểm tra lại một lần nữa các giá trị thiếu trong các cột còn lại
    print("\nKiểm tra dữ liệu thiếu còn lại (nếu có):")
    remaining_missing = final_df.isnull().sum()
    print(remaining_missing[remaining_missing > 0])

    # Lưu kết quả
    final_df.to_csv(OUTPUT_FILE_PATH, index=False)
    print(f"\nĐã lưu bộ dữ liệu cuối cùng tại: '{OUTPUT_FILE_PATH}'")
    print(">>> BƯỚC TIẾP THEO: Feature Engineering trên file này. <<<")


if __name__ == "__main__":
    main()