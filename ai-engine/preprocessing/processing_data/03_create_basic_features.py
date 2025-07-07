import pandas as pd
import numpy as np
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN ---
# Giả sử script này nằm trong thư mục con, chúng ta đi lên 1 cấp để vào thư mục gốc của project
BASE_DIR = Path(__file__).resolve().parent.parent.parent 
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
INPUT_FILENAME = "final_cleaned_data.csv"
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME
OUTPUT_FILENAME = "features_part1.csv"
OUTPUT_FILE_PATH = PROCESSED_DATA_DIR / OUTPUT_FILENAME




def create_betting_features(df):
    """Tạo các đặc trưng từ tỷ lệ cược (Task 3.4)."""
    print("  - Creating betting odds features...")
    
    odds_sources = {
        'b365': ['B365H', 'B365D', 'B365A'],
        'ps_close': ['PSCH', 'PSCD', 'PSCA'],
        'ps_open': ['PSH', 'PSD', 'PSA']
    }

    for source, cols in odds_sources.items():
        H, D, A = cols[0], cols[1], cols[2]
        if all(c in df.columns for c in cols):
            prob_h_col = f'prob_{source}_h'
            prob_d_col = f'prob_{source}_d'
            prob_a_col = f'prob_{source}_a'
            
            # Chuyển Odds thành Xác suất
            df[prob_h_col] = 1 / df[H]
            df[prob_d_col] = 1 / df[D]
            df[prob_a_col] = 1 / df[A]
            
            # Tính Margin (lợi nhuận nhà cái)
            df[f'margin_{source}'] = df[[prob_h_col, prob_d_col, prob_a_col]].sum(axis=1) - 1
            
            # Tính chênh lệch xác suất
            df[f'prob_diff_{source}'] = df[prob_h_col] - df[prob_a_col]

    # [NÂNG CẤP] Tính Odds Consensus (trung bình tỷ lệ cược từ các nhà cái chính)
    if all(c in df.columns for c in ['B365H', 'PSH']):
        df['odds_consensus_h'] = df[['B365H', 'PSH']].mean(axis=1)
        df['odds_consensus_d'] = df[['B365D', 'PSD']].mean(axis=1)
        df['odds_consensus_a'] = df[['B365A', 'PSA']].mean(axis=1)

    # Tính sự dịch chuyển của thị trường (dùng Pinnacle)
    if all(c in df.columns for c in ['PSCH', 'PSH', 'PSCD', 'PSD', 'PSCA', 'PSA']):
        df['odds_movement_h'] = df['PSCH'] - df['PSH']
        df['odds_movement_d'] = df['PSCD'] - df['PSD']
        df['odds_movement_a'] = df['PSCA'] - df['PSA']

    return df

def create_time_features(df):
    """Tạo các đặc trưng liên quan đến thời gian (Task 3.5)."""
    print("  - Creating time context features...")
    
    df['date_month'] = df['Date'].dt.month
    df['date_day_of_week'] = df['Date'].dt.dayofweek # Monday=0, Sunday=6
    df['date_is_weekend'] = (df['date_day_of_week'] >= 5).astype(int)

    def get_season_stage(month):
        if month in [8, 9, 10]: return 'early'
        elif month in [11, 12, 1, 2]: return 'mid'
        else: return 'late'
            
    df['season_stage'] = df['date_month'].apply(get_season_stage)
    # One-hot encode để mô hình có thể sử dụng
    df = pd.get_dummies(df, columns=['season_stage'], prefix='stage', dtype=int)
    
    return df

def main():
    """Hàm chính để chạy toàn bộ quy trình."""
    print("--- SCRIPT 04: BẮT ĐẦU TẠO ĐẶC TRƯNG CƠ BẢN ---")
    
    try:
        df = pd.read_csv(INPUT_FILE_PATH, parse_dates=['Date'])
        print(f"1. Đã đọc thành công file '{INPUT_FILENAME}'.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file '{INPUT_FILE_PATH}'.")
        return

    print("2. Bắt đầu tạo các nhóm đặc trưng:")
    df = create_betting_features(df)
    df = create_time_features(df)
    
    df.to_csv(OUTPUT_FILE_PATH, index=False)
    print("\n--- HOÀN TẤT ---")
    print(f"Đã lưu file với các đặc trưng cơ bản tại: '{OUTPUT_FILENAME}'")
    print(f"File output có {df.shape[0]} dòng và {df.shape[1]} cột.")

if __name__ == "__main__":
    main()