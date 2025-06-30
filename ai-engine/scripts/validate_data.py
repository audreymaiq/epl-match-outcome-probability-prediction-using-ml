# ai-engine/scripts/validate_data.py

import pandas as pd
from sqlalchemy import create_engine
import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path để có thể import các module khác
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Bây giờ mới import
from config.settings import get_config

def validate_data():
    """
    Xác thực dữ liệu trong database bằng cách sử dụng đúng tên bảng và tên cột
    từ file schema init-db.sql.
    """
    print("--- Bắt đầu xác thực dữ liệu (Sử dụng đúng Schema) ---")
    try:
        # Lấy cấu hình
        config = get_config()

        # Tạo chuỗi kết nối DB một cách chính xác
        db_url = config.db.dsn
        print("Đang kết nối tới database...")
        engine = create_engine(db_url)

        # 1. Đọc dữ liệu từ DB vào Pandas DataFrame
        #    Câu lệnh SQL đã được sửa để khớp 100% với schema.
        query = """
        SELECT
            m."id" AS "internal_match_id",
            em."external_id",
            m."match_datetime" AS "start_time",
            m."status",
            s."name" AS "season_name",
            home_team."name" AS "home_team_name",
            away_team."name" AS "away_team_name",
            m."home_goals" AS "home_score",
            m."away_goals" AS "away_score"
        FROM "Matches" AS m
        JOIN "Seasons" AS s ON m."season_id" = s."id"
        JOIN "Teams" AS home_team ON m."home_team_id" = home_team."id"
        JOIN "Teams" AS away_team ON m."away_team_id" = away_team."id"
        LEFT JOIN "ExternalMapping" AS em ON m."id" = em."internal_id" AND em."entity_type" = 'match' AND em."source_system" = 'sofascore'
        """
        df_matches = pd.read_sql(query, engine)
        print(f"Đã tải {len(df_matches)} trận đấu vào DataFrame.")

        if df_matches.empty:
            print("CẢNH BÁO: Không có dữ liệu trận đấu nào trong database để xác thực.")
            return

        # Đổi tên cột trong DataFrame để code bên dưới hoạt động
        # (Pandas sẽ dùng tên alias từ câu SQL)
        # Không cần nữa vì đã dùng AS trong SQL

        # 2. Kiểm tra số lượng Null
        print("\n--- Kiểm tra giá trị Null ---")
        null_counts = df_matches.isnull().sum()
        print(null_counts[null_counts > 0])
        # Kỳ vọng: external_id có thể có null nếu mapping chưa có.

        # 3. Phân tích phân phối
        print("\n--- Thống kê cơ bản về tỉ số ---")
        print(df_matches[['home_score', 'away_score']].describe())

        # 4. Kiểm tra tính nhất quán
        print("\n--- Phân phối trạng thái trận đấu ---")
        print(df_matches['status'].value_counts())

        print("\n--- Kiểm tra số trận mỗi mùa ---")
        matches_per_season = df_matches.groupby('season_name').size()
        print(matches_per_season)
        print("Lưu ý: Một mùa giải Premier League đầy đủ có 380 trận.")

        print("\n--- Kiểm tra số trận mỗi đội trong một mùa giải cụ thể ---")
        last_season = matches_per_season.index[-1]
        df_last_season = df_matches[df_matches['season_name'] == last_season]
        
        home_games = df_last_season.groupby('home_team_name').size()
        away_games = df_last_season.groupby('away_team_name').size()
        total_games = home_games.add(away_games, fill_value=0).sort_values()
        
        print(f"Số trận mỗi đội trong mùa {last_season}:")
        print(total_games)

        print("\n--- Xác thực dữ liệu hoàn tất ---")

    except Exception as e:
        print(f"\nLỖI: Đã xảy ra lỗi trong quá trình xác thực: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    validate_data()