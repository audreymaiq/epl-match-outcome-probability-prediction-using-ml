import pandas as pd
import numpy as np
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Đi lên một cấp
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
INPUT_FILENAME = "features_part2_advanced.csv"
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME
OUTPUT_FILENAME = "model_training_dataset.csv"
OUTPUT_FILE_PATH = PROCESSED_DATA_DIR / OUTPUT_FILENAME

def create_difference_features(df):
    """Tạo các đặc trưng chênh lệch giữa đội nhà và đội khách."""
    print("  - Creating difference features (Home vs Away)...")
    
    home_cols = [col for col in df.columns if col.endswith('_H')]
    for col_h in home_cols:
        col_base = col_h[:-2] # Bỏ '_H'
        col_a = f'{col_base}_A'
        if col_a in df.columns:
            df[f'diff_{col_base}'] = df[col_h] - df[col_a]
    return df

def main():
    """Hàm chính để chạy toàn bộ quy trình."""
    print("--- SCRIPT 06: BẮT ĐẦU TẠO ĐẶC TRƯNG TỔNG HỢP & CHỌN LỌC ---")
    
    try:
        df = pd.read_csv(INPUT_FILE_PATH, parse_dates=['Date'])
        print(f"1. Đã đọc thành công file '{INPUT_FILENAME}'.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file '{INPUT_FILE_PATH}'.")
        return

    df = create_difference_features(df)
    
    print("\n2. Hoàn tất và chuẩn bị bộ dữ liệu cuối cùng...")
    
    # CHỌN LỌC ĐẶC TRƯNG CUỐI CÙNG
    # Đây là nơi bạn quyết định đặc trưng nào sẽ được đưa vào mô hình
    
    # 1. Các cột thông tin và biến mục tiêu
    core_cols = ['Date', 'HomeTeam', 'AwayTeam', 'Season', 'FTR', 'FTHG', 'FTAG']

    # 2. Đặc trưng tốt nhất từ tỷ lệ cược
    betting_features = [
        'prob_diff_b365', 'prob_diff_ps_close', 'odds_movement_h', 'odds_movement_a'
    ]

    # 3. Đặc trưng tốt nhất về phong độ (chênh lệch)
    form_features = [
        'diff_avg_Points_overall_last_5', 'diff_avg_GoalsScored_overall_last_5', 
        'diff_avg_GoalsConceded_overall_last_5', 'diff_avg_ShotsOnTarget_overall_last_5'
    ]

    # 4. Đặc trưng tốt nhất về BXH (proxy) và thể lực
    season_features = [
        'diff_points_per_game_season', 'diff_cum_goal_diff_season', 'diff_days_since_last_match'
    ]
    
    # 5. Đặc trưng H2H
    h2h_features = ['h2h_home_win_rate', 'h2h_btts_rate', 'h2h_over25_rate']
    
    final_feature_list = core_cols + betting_features + form_features + season_features + h2h_features
    
    # Lọc ra những cột thực sự tồn tại để tránh lỗi
    final_df_for_model = df[[col for col in final_feature_list if col in df.columns]].copy()

    # Lưu kết quả
    final_df_for_model.to_csv(OUTPUT_FILE_PATH, index=False)
    print(f"\nĐÃ TẠO BỘ DỮ LIỆU CUỐI CÙNG ĐỂ HUẤN LUYỆN!")
    print(f"File được lưu tại: '{OUTPUT_FILENAME}'")
    print(f"Bộ dữ liệu có {final_df_for_model.shape[0]} dòng và {final_df_for_model.shape[1]} cột.")


if __name__ == "__main__":
    main()