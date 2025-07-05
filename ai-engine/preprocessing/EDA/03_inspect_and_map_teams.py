import pandas as pd
from pathlib import Path

# --- CẤU HÌNH ---
# Xác định thư mục gốc của dự án ('ai-engine') bằng cách đi lùi 3 cấp từ vị trí file script
# .../scripts/data_exploration/03_... -> .../scripts/data_exploration -> .../scripts -> .../ai-engine
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent # Đây là thư mục gốc của dự án

# Bây giờ, xây dựng đường dẫn đúng dựa trên thư mục gốc
DATA_DIR = PROJECT_ROOT / "data" # Thư mục chứa dữ liệu thô
PROCESSED_DATA_DIR = DATA_DIR / "processed" # Thư mục chứa dữ liệu đã gộp các mùa giải

# Tên file không đổi
INPUT_FILENAME = "combined_seasons.csv"
MAPPING_FILENAME = "team_mapping.csv"

# Đường dẫn cuối cùng đến các file
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME
MAPPING_FILE_PATH = PROCESSED_DATA_DIR / MAPPING_FILENAME

def inspect_and_create_mapping():
    """
    Đọc file đã hợp nhất, trích xuất tên đội, và tạo file mapping để người dùng chỉnh sửa.
    """
    print("--- BẮT ĐẦU KIỂM TRA TÊN ĐỘI ---")

    # --- BƯỚC 1: ĐỌC DỮ LIỆU ĐÃ HỢP NHẤT ---
    try:
        df = pd.read_csv(INPUT_FILE_PATH)
        print(f"1. Đã đọc thành công file '{INPUT_FILENAME}'.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file '{INPUT_FILE_PATH}'.")
        print("Vui lòng đảm bảo bạn đã chạy script hợp nhất dữ liệu trước.")
        return
    except Exception as e:
        print(f"Lỗi khi đọc file: {e}")
        return

    # --- BƯỚC 2: TRÍCH XUẤT VÀ IN DANH SÁCH TÊN ĐỘI ---
    print("\n--- 2. Trích xuất tất cả các tên đội duy nhất ---")
    
    # Kiểm tra xem cột 'HomeTeam' và 'AwayTeam' có tồn tại không
    if 'HomeTeam' not in df.columns or 'AwayTeam' not in df.columns:
        print("LỖI: Không tìm thấy cột 'HomeTeam' hoặc 'AwayTeam' trong file.")
        return

    unique_home_teams = set(df['HomeTeam'].dropna().unique())
    unique_away_teams = set(df['AwayTeam'].dropna().unique())
    all_unique_teams = sorted(list(unique_home_teams.union(unique_away_teams)))

    print(f"Tìm thấy tổng cộng {len(all_unique_teams)} tên đội duy nhất.")
    print("Vui lòng kiểm tra danh sách bên dưới để tìm các tên không nhất quán:")
    # In ra thành nhiều cột để dễ nhìn hơn
    teams_per_line = 5
    for i in range(0, len(all_unique_teams), teams_per_line):
        print(" | ".join(f"{team:<25}" for team in all_unique_teams[i:i+teams_per_line]))

    # --- BƯỚC 3: TẠO FILE MAPPING ĐỂ CHỈNH SỬA ---
    print(f"\n--- 3. Tạo file mapping tại '{MAPPING_FILE_PATH}' ---")

    # Tạo một DataFrame cho việc mapping
    mapping_df = pd.DataFrame({
        'original_name': all_unique_teams,
        'standard_name': all_unique_teams  # Mặc định, tên chuẩn là chính nó
    })

    # Lưu file mapping này
    mapping_df.to_csv(MAPPING_FILE_PATH, index=False)

    print("\n>>> HÀNH ĐỘNG TIẾP THEO <<<")
    print("1. Mở file 'team_mapping.csv' trong thư mục 'processed'.")
    print("2. Đối với mỗi đội có nhiều tên (ví dụ: 'Wolves' và 'Wolverhampton Wanderers'),")
    print("   hãy chọn một tên làm chuẩn và điền vào cột 'standard_name' cho tất cả các biến thể.")
    print("   Ví dụ:")
    print("   original_name,standard_name")
    print("   ...,...")
    print("   Wolves,Wolverhampton Wanderers")
    print("   Wolverhampton Wanderers,Wolverhampton Wanderers")
    print("   ...,...")
    print("3. Sau khi chỉnh sửa và lưu file, bạn có thể dùng file này để chuẩn hóa dữ liệu ở bước tiếp theo.")

if __name__ == "__main__":
    inspect_and_create_mapping()