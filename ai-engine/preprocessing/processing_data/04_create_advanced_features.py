import pandas as pd
import numpy as np
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Đi lên một cấp
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
INPUT_FILENAME = "features_part1.csv"
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME
OUTPUT_FILENAME = "features_part2_advanced.csv"
OUTPUT_FILE_PATH = PROCESSED_DATA_DIR / OUTPUT_FILENAME


def get_team_level_data(df):
    """Chuyển đổi DataFrame sang dạng "dài" (team-centric) để tính toán."""
    df['home_win'] = (df['FTR'] == 'H').astype(int)
    df['away_win'] = (df['FTR'] == 'A').astype(int)
    df['is_draw'] = (df['FTR'] == 'D').astype(int)
    df['btts'] = ((df['FTHG'] > 0) & (df['FTAG'] > 0)).astype(int) # Both Teams To Score
    df['over_2_5'] = (df['FTHG'] + df['FTAG'] > 2.5).astype(int)
    
    common_cols = ['Date', 'Season', 'FTR', 'home_win', 'away_win', 'is_draw', 'btts', 'over_2_5']
    home_cols = common_cols + ['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HS', 'AS', 'HST', 'AST']
    away_cols = common_cols + ['AwayTeam', 'HomeTeam', 'FTAG', 'FTHG', 'AS', 'HS', 'AST', 'HST']
    
    home_df, away_df = df[home_cols].copy(), df[away_cols].copy()
    
    new_col_names = ['Date', 'Season', 'FTR', 'home_win', 'away_win', 'is_draw', 'btts', 'over_2_5', 
                     'Team', 'Opponent', 'GoalsScored', 'GoalsConceded', 
                     'Shots', 'ShotsAllowed', 'ShotsOnTarget', 'ShotsOnTargetAllowed']
                     
    home_df.columns, away_df.columns = new_col_names, new_col_names
    home_df['Venue'], away_df['Venue'] = 'H', 'A'
    home_df['Points'], away_df['Points'] = np.where(home_df['FTR'] == 'H', 3, np.where(home_df['FTR'] == 'D', 1, 0)), np.where(away_df['FTR'] == 'A', 3, np.where(away_df['FTR'] == 'D', 1, 0))
    home_df['Win'], away_df['Win'] = home_df['home_win'], away_df['away_win']
    home_df['CleanSheet'] = (home_df['GoalsConceded'] == 0).astype(int)
    away_df['CleanSheet'] = (away_df['GoalsConceded'] == 0).astype(int)

    team_df = pd.concat([home_df, away_df], ignore_index=True)
    team_df = team_df.sort_values(['Team', 'Date']).reset_index(drop=True)
    return team_df

def calculate_rolling_features(team_df, windows=[5, 10], venue_specific=False):
    """Tính các đặc trưng phong độ. Có thể tính chung hoặc theo địa điểm."""
    group_cols = ['Team']
    prefix = 'overall'
    if venue_specific:
        group_cols.append('Venue')
        prefix = 'venue'

    print(f"  - Calculating {'venue-specific' if venue_specific else 'overall'} rolling features...")
    
    cols_to_roll = ['GoalsScored', 'GoalsConceded', 'Points', 'Win', 'Shots', 'ShotsOnTarget', 'CleanSheet']
    for window in windows:
        for col in cols_to_roll:
            team_df[f'avg_{col}_{prefix}_last_{window}'] = team_df.groupby(group_cols)[col].transform(
                lambda x: x.rolling(window, min_periods=1).mean().shift(1))
    return team_df

def calculate_cumulative_and_streak_features(team_df):
    """Tính các đặc trưng tích lũy (proxy cho BXH) và chuỗi trận."""
    print("  - Calculating cumulative season and streak features...")
    
    # Tích lũy cả mùa
    team_df['matches_played_season'] = team_df.groupby(['Season', 'Team']).cumcount()
    team_df['points_per_game_season'] = team_df.groupby(['Season', 'Team'])['Points'].transform(lambda x: x.expanding().mean().shift(1))
    team_df['goal_diff_season'] = (team_df['GoalsScored'] - team_df['GoalsConceded'])
    team_df['cum_goal_diff_season'] = team_df.groupby(['Season', 'Team'])['goal_diff_season'].transform(lambda x: x.expanding().sum().shift(1))

    # Chuỗi trận
    team_df['win_streak'] = team_df.groupby('Team')['Win'].transform(lambda x: x * (x.groupby((x != x.shift()).cumsum()).cumcount() + 1)).shift(1)
    team_df['undefeated'] = (team_df['Points'] > 0).astype(int)
    team_df['undefeated_streak'] = team_df.groupby('Team')['undefeated'].transform(lambda x: x * (x.groupby((x != x.shift()).cumsum()).cumcount() + 1)).shift(1)
    
    # Ngày nghỉ
    team_df['days_since_last_match'] = team_df.groupby('Team')['Date'].diff().dt.days

    return team_df

def create_h2h_features(df):
    """Tính các đặc trưng về lịch sử đối đầu."""
    print("  - Calculating Head-to-Head (H2H) features...")
    
    df['matchup'] = df.apply(lambda row: tuple(sorted((row['HomeTeam'], row['AwayTeam']))), axis=1)
    h2h_stats = df.copy().sort_values('Date')
    
    h2h_stats['h2h_matches_played'] = h2h_stats.groupby('matchup').cumcount()
    # Chỉ tính khi đã có ít nhất 1 trận H2H
    h2h_stats.loc[h2h_stats['h2h_matches_played'] > 0, 'h2h_home_win_rate'] = (h2h_stats.groupby('matchup')['home_win'].cumsum().shift(1) / h2h_stats['h2h_matches_played'])
    h2h_stats.loc[h2h_stats['h2h_matches_played'] > 0, 'h2h_btts_rate'] = (h2h_stats.groupby('matchup')['btts'].cumsum().shift(1) / h2h_stats['h2h_matches_played'])
    h2h_stats.loc[h2h_stats['h2h_matches_played'] > 0, 'h2h_over25_rate'] = (h2h_stats.groupby('matchup')['over_2_5'].cumsum().shift(1) / h2h_stats['h2h_matches_played'])

    h2h_cols_to_merge = [col for col in h2h_stats.columns if 'h2h_' in col]
    key_cols = ['Date', 'HomeTeam', 'AwayTeam']
    df = pd.merge(df, h2h_stats[key_cols + h2h_cols_to_merge], on=key_cols, how='left')
    return df

def main():
    print("--- SCRIPT 05: BẮT ĐẦU TẠO ĐẶC TRƯNG NÂNG CAO ---")
    
    try:
        df = pd.read_csv(INPUT_FILE_PATH, parse_dates=['Date'])
        print(f"1. Đã đọc thành công file '{INPUT_FILENAME}'.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file '{INPUT_FILE_PATH}'.")
        return

    team_df = get_team_level_data(df)
    
    # Tính toán các loại features
    team_df = calculate_rolling_features(team_df, windows=[5, 10], venue_specific=False) # Phong độ chung
    team_df = calculate_rolling_features(team_df, windows=[5, 10], venue_specific=True) # Phong độ theo địa điểm
    team_df = calculate_cumulative_and_streak_features(team_df)
    
    # Gộp features trở lại
    feature_cols = [col for col in team_df.columns if any(p in col for p in ['avg_', 'cum_', 'streak', 'matches_played', 'points_per_game', 'days_since'])]
    key_cols = ['Date', 'Team']
    team_features = team_df[key_cols + feature_cols].drop_duplicates(subset=key_cols, keep='last')

    df = pd.merge(df, team_features, left_on=['Date', 'HomeTeam'], right_on=['Date', 'Team'], how='left').rename(columns={col: f'{col}_H' for col in feature_cols}).drop(columns='Team')
    df = pd.merge(df, team_features, left_on=['Date', 'AwayTeam'], right_on=['Date', 'Team'], how='left').rename(columns={col: f'{col}_A' for col in feature_cols}).drop(columns='Team')
    
    df = create_h2h_features(df)
    
    df.fillna(0, inplace=True)
    df.to_csv(OUTPUT_FILE_PATH, index=False)
    print("\n--- HOÀN TẤT ---")
    print(f"Đã lưu bộ dữ liệu với đầy đủ đặc trưng tại: '{OUTPUT_FILENAME}'")
    print(f"Bộ dữ liệu có {df.shape[0]} dòng và {df.shape[1]} cột.")


if __name__ == "__main__":
    main()