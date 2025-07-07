# filename: predict_new_match.py

import pandas as pd
import numpy as np
import joblib
from pathlib import Path

# --- CẤU HÌNH ---
# Giả sử script này nằm trong thư mục gốc của dự án
BASE_DIR = Path(__file__).resolve().parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"
BEST_MODEL_DIR = MODEL_DIR / "best_models"

# ---------------------------------------------------------------------------- #
#  CÁC HÀM TẠO ĐẶC TRƯNG - SAO CHÉP TỪ CÁC SCRIPT TRƯỚC ĐỂ ĐẢM BẢO TÍNH NHẤT QUÁN  #
# ---------------------------------------------------------------------------- #

# Các hàm từ 03_create_basic_features.py (hoặc 04 theo cách đánh số cũ)
def create_betting_features(df):
    odds_sources = {'b365': ['B365H', 'B365D', 'B365A'], 'ps_close': ['PSCH', 'PSCD', 'PSCA'], 'ps_open': ['PSH', 'PSD', 'PSA']}
    for source, cols in odds_sources.items():
        H, D, A = cols[0], cols[1], cols[2]
        if all(c in df.columns for c in cols):
            prob_h, prob_d, prob_a = f'prob_{source}_h', f'prob_{source}_d', f'prob_{source}_a'
            df[prob_h], df[prob_d], df[prob_a] = 1/df[H], 1/df[D], 1/df[A]
            df[f'margin_{source}'] = df[[prob_h, prob_d, prob_a]].sum(axis=1) - 1
            df[f'prob_diff_{source}'] = df[prob_h] - df[prob_a]
    if all(c in df.columns for c in ['PSCH', 'PSH']): df['odds_movement_h'] = df['PSCH'] - df['PSH']
    if all(c in df.columns for c in ['PSCD', 'PSD']): df['odds_movement_d'] = df['PSCD'] - df['PSD']
    if all(c in df.columns for c in ['PSCA', 'PSA']): df['odds_movement_a'] = df['PSCA'] - df['PSA']
    return df

def create_time_features(df):
    df['date_month'] = df['Date'].dt.month
    df['date_day_of_week'] = df['Date'].dt.dayofweek
    df['date_is_weekend'] = (df['date_day_of_week'] >= 5).astype(int)
    def get_season_stage(month):
        if month in [8, 9, 10]: return 'early';
        elif month in [11, 12, 1, 2]: return 'mid';
        else: return 'late'
    df['season_stage'] = df['date_month'].apply(get_season_stage)
    df = pd.get_dummies(df, columns=['season_stage'], prefix='stage', dtype=int)
    return df

# Các hàm từ 04_create_advanced_features.py
def get_team_level_data(df):
    df['home_win'] = (df['FTR'] == 'H').astype(int)
    df['away_win'] = (df['FTR'] == 'A').astype(int)
    df['is_draw'] = (df['FTR'] == 'D').astype(int)
    df['btts'] = ((df['FTHG'] > 0) & (df['FTAG'] > 0)).astype(int)
    df['over_2_5'] = (df['FTHG'] + df['FTAG'] > 2.5).astype(int)
    common_cols = ['Date', 'Season', 'FTR', 'home_win', 'away_win', 'is_draw', 'btts', 'over_2_5']
    home_cols, away_cols = common_cols + ['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HS', 'AS', 'HST', 'AST'], common_cols + ['AwayTeam', 'HomeTeam', 'FTAG', 'FTHG', 'AS', 'HS', 'AST', 'HST']
    home_df, away_df = df[home_cols].copy(), df[away_cols].copy()
    new_col_names = ['Date', 'Season', 'FTR', 'home_win', 'away_win', 'is_draw', 'btts', 'over_2_5', 'Team', 'Opponent', 'GoalsScored', 'GoalsConceded', 'Shots', 'ShotsAllowed', 'ShotsOnTarget', 'ShotsOnTargetAllowed']
    home_df.columns, away_df.columns = new_col_names, new_col_names
    home_df['Venue'], away_df['Venue'] = 'H', 'A'
    home_df['Points'], away_df['Points'] = np.where(home_df['FTR'] == 'H', 3, np.where(home_df['FTR'] == 'D', 1, 0)), np.where(away_df['FTR'] == 'A', 3, np.where(away_df['FTR'] == 'D', 1, 0))
    home_df['Win'], away_df['Win'] = home_df['home_win'], away_df['away_win']
    home_df['CleanSheet'], away_df['CleanSheet'] = (home_df['GoalsConceded'] == 0).astype(int), (away_df['GoalsConceded'] == 0).astype(int)
    team_df = pd.concat([home_df, away_df], ignore_index=True).sort_values(['Team', 'Date']).reset_index(drop=True)
    return team_df

def calculate_rolling_features(team_df, windows=[5, 10], venue_specific=False):
    group_cols, prefix = ['Team'], 'overall'
    if venue_specific: group_cols.append('Venue'); prefix = 'venue'
    cols_to_roll = ['GoalsScored', 'GoalsConceded', 'Points', 'Win', 'Shots', 'ShotsOnTarget', 'CleanSheet']
    for window in windows:
        for col in cols_to_roll:
            team_df[f'avg_{col}_{prefix}_last_{window}'] = team_df.groupby(group_cols)[col].transform(lambda x: x.rolling(window, min_periods=1).mean().shift(1))
    return team_df

def calculate_cumulative_features(team_df):
    team_df['matches_played_season'] = team_df.groupby(['Season', 'Team']).cumcount()
    team_df['points_per_game_season'] = team_df.groupby(['Season', 'Team'])['Points'].transform(lambda x: x.expanding().mean().shift(1))
    team_df['goal_diff_season'] = (team_df['GoalsScored'] - team_df['GoalsConceded'])
    team_df['cum_goal_diff_season'] = team_df.groupby(['Season', 'Team'])['goal_diff_season'].transform(lambda x: x.expanding().sum().shift(1))
    team_df['days_since_last_match'] = team_df.groupby('Team')['Date'].diff().dt.days
    return team_df

def create_h2h_features(df):
    df['matchup'] = df.apply(lambda row: tuple(sorted((row['HomeTeam'], row['AwayTeam']))), axis=1)
    h2h_stats = df.copy().sort_values('Date')
    h2h_stats['h2h_matches_played'] = h2h_stats.groupby('matchup').cumcount()
    if h2h_stats['h2h_matches_played'].sum() > 0:
        h2h_stats['h2h_home_win_rate'] = (h2h_stats.groupby('matchup')['home_win'].cumsum().shift(1) / h2h_stats['h2h_matches_played'])
        h2h_stats['h2h_btts_rate'] = (h2h_stats.groupby('matchup')['btts'].cumsum().shift(1) / h2h_stats['h2h_matches_played'])
        h2h_stats['h2h_over25_rate'] = (h2h_stats.groupby('matchup')['over_2_5'].cumsum().shift(1) / h2h_stats['h2h_matches_played'])
    h2h_cols_to_merge = [col for col in h2h_stats.columns if 'h2h_' in col]
    key_cols = ['Date', 'HomeTeam', 'AwayTeam']
    df = pd.merge(df, h2h_stats[key_cols + h2h_cols_to_merge], on=key_cols, how='left')
    return df

# Hàm từ 05_create_composite_features.py
def create_difference_features(df):
    home_cols = [col for col in df.columns if col.endswith('_H')]
    for col_h in home_cols:
        col_base, col_a = col_h[:-2], f'{col_h[:-2]}_A'
        if col_a in df.columns: df[f'diff_{col_base}'] = df[col_h] - df[col_a]
    return df

# ------------------------------------------------------------------------- #
#              HÀM DỰ ĐOÁN CHÍNH (THE INFERENCE PIPELINE)                   #
# ------------------------------------------------------------------------- #

def predict_match(home_team: str, away_team: str, match_date_str: str, historical_df: pd.DataFrame):
    """
    Dự đoán kết quả cho một trận đấu mới.
    """
    print(f"\n--- Bắt đầu dự đoán cho trận: {home_team} vs {away_team} vào ngày {match_date_str} ---")
    
    # 1. Chuẩn bị dữ liệu
    match_date = pd.to_datetime(match_date_str)
    # Lấy TẤT CẢ dữ liệu lịch sử TRƯỚC ngày trận đấu
    df_history = historical_df[historical_df['Date'] < match_date].copy()
    
    # Tạo một dòng dữ liệu tạm cho trận đấu mới để nối vào cuối
    new_match_data = {'Date': [match_date], 'HomeTeam': [home_team], 'AwayTeam': [away_team]}
    new_match_df = pd.DataFrame(new_match_data)
    
    # Nối trận mới vào cuối dữ liệu lịch sử để tính toán
    full_df = pd.concat([df_history, new_match_df], ignore_index=True)
    
    # 2. Tái tạo lại toàn bộ quy trình Feature Engineering
    print("   -> Tái tạo các đặc trưng...")
    
    # Lấy các odds gần nhất cho trận đấu mới (giả định)
    # Trong thực tế, bạn sẽ lấy odds từ API
    last_home_odds = df_history[df_history['HomeTeam'] == home_team].iloc[-1]
    last_away_odds = df_history[df_history['AwayTeam'] == away_team].iloc[-1]
    odds_cols = [c for c in df_history.columns if any(p in c for p in ['B365', 'PSH', 'PSD', 'PSA', 'PSCH', 'PSCD', 'PSCA'])]
    for col in odds_cols:
        # Ưu tiên lấy odds từ lần gần nhất đội đó đá
        if col.startswith(('B365H', 'PSH', 'PSCH')):
            full_df.loc[full_df.index[-1], col] = last_home_odds[col]
        elif col.startswith(('B365A', 'PSA', 'PSCA')):
            full_df.loc[full_df.index[-1], col] = last_away_odds[col]
        else: # B365D, PSD
            full_df.loc[full_df.index[-1], col] = last_home_odds[col]

    full_df = create_betting_features(full_df)
    
    team_df = get_team_level_data(full_df)
    team_df = calculate_rolling_features(team_df, windows=[5, 10], venue_specific=False)
    team_df = calculate_rolling_features(team_df, windows=[5, 10], venue_specific=True)
    team_df = calculate_cumulative_features(team_df)
    
    feature_cols = [col for col in team_df.columns if any(p in col for p in ['avg_', 'cum_', 'matches_played', 'points_per_game', 'days_since'])]
    team_features = team_df[['Date', 'Team'] + feature_cols].drop_duplicates(subset=['Date', 'Team'], keep='last')
    
    full_df = pd.merge(full_df, team_features, left_on=['Date', 'HomeTeam'], right_on=['Date', 'Team'], how='left').rename(columns={col: f'{col}_H' for col in feature_cols}).drop(columns='Team')
    full_df = pd.merge(full_df, team_features, left_on=['Date', 'AwayTeam'], right_on=['Date', 'Team'], how='left').rename(columns={col: f'{col}_A' for col in feature_cols}).drop(columns='Team')
    
    full_df = create_h2h_features(full_df)
    full_df = create_difference_features(full_df)
    full_df.fillna(0, inplace=True)

    # 3. Trích xuất dòng đặc trưng cuối cùng cho trận đấu mới
    match_features = full_df.iloc[-1:]
    
    # 4. Tải mô hình và dự đoán
    print("   -> Tải mô hình và đưa ra dự đoán...")
    pipeline = joblib.load(BEST_MODEL_DIR / "best_lr_pipeline.pkl")
    le = joblib.load(MODEL_DIR / "baseline_models" / "label_encoder.pkl")
    
    X_predict = match_features.drop(columns=['Date', 'HomeTeam', 'AwayTeam', 'FTR', 'FTHG', 'FTAG', 'Season', 'btts', 'over_2_5', 'home_win', 'away_win', 'is_draw', 'matchup'], errors='ignore')
    
    # Đảm bảo các cột của X_predict khớp với các cột mô hình đã được huấn luyện
    # Lấy danh sách cột từ scaler trong pipeline
    trained_cols = pipeline.named_steps['scaler'].get_feature_names_out()
    X_predict = X_predict[trained_cols]
    
    probabilities = pipeline.predict_proba(X_predict)[0]
    
    # 5. Trình bày kết quả
    results = {label: prob for label, prob in zip(le.classes_, probabilities)}
    
    print("\n--- KẾT QUẢ DỰ ĐOÁN ---")
    for outcome, prob in results.items():
        print(f"   Xác suất cho kết quả '{outcome}': {prob:.2%}")
        
    predicted_outcome = le.inverse_transform([np.argmax(probabilities)])[0]
    print(f"\n   ==> DỰ ĐOÁN CUỐI CÙNG: '{predicted_outcome}'")
    
    return results

if __name__ == '__main__':
    # --- TẢI DỮ LIỆU LỊCH SỬ MỘT LẦN ---
    try:
        historical_data = pd.read_csv(PROCESSED_DATA_DIR / "final_cleaned_data.csv", parse_dates=['Date'])
        print("Đã tải dữ liệu lịch sử thành công.")
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file 'final_cleaned_data.csv'. Vui lòng chạy các script tiền xử lý trước.")
        exit()

    # --- VÍ DỤ SỬ DỤNG ---
    # Dự đoán cho một trận đấu trong tương lai
    predict_match(
        home_team="Man City", 
        away_team="Arsenal", 
        match_date_str="2024-08-18", 
        historical_df=historical_data
    )
    
    # Dự đoán cho một trận đấu khác
    predict_match(
        home_team="Liverpool", 
        away_team="Man United", 
        match_date_str="2024-09-01", 
        historical_df=historical_data
    )