import pandas as pd
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN ĐỘNG ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


def main():
    """
    Thực hiện bước đầu tiên của quy trình:
    1. Tải các file CSV.
    2. Chèn cột 'Season' vào vị trí thứ hai.
    3. Hợp nhất tất cả thành một DataFrame.
    4. Lưu kết quả ra file mới.
    """
    print("--- BƯỚC 1: TẢI VÀ HỢP NHẤT DỮ LIỆU THÔ ---")
    print(f"Đọc dữ liệu từ: {DATA_DIR}")
    
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        csv_files = sorted([f for f in DATA_DIR.glob("*.csv")])
        if not csv_files:
            raise FileNotFoundError(f"Không tìm thấy file CSV nào trong thư mục '{DATA_DIR}'.")
        print(f"Tìm thấy {len(csv_files)} file CSV để xử lý.")
    except FileNotFoundError as e:
        print(f"Lỗi: {e}")
        return

    all_seasons_dfs = []
    for file_path in csv_files:
        try:
            df = pd.read_csv(file_path, low_memory=False, encoding='ISO-8859-1')
            
            # --- THAY ĐỔI Ở ĐÂY ---
            # Lấy tên mùa giải từ tên file
            season_name = file_path.stem
            
            # Kiểm tra xem cột 'Div' có tồn tại không để xác định vị trí chèn
            if 'Div' in df.columns:
                # Chèn cột 'Season' vào vị trí 1 (ngay sau cột 'Div' ở vị trí 0)
                df.insert(1, 'Season', season_name)
                print(f"  - Đã đọc và chèn cột 'Season' vào sau 'Div' cho file: {file_path.name}")
            else:
                # Nếu không có cột 'Div', chèn 'Season' vào vị trí đầu tiên
                df.insert(0, 'Season', season_name)
                print(f"  - CẢNH BÁO: Không tìm thấy cột 'Div'. Chèn 'Season' vào đầu cho file: {file_path.name}")
            
            all_seasons_dfs.append(df)
            
        except Exception as e:
            print(f"  - LỖI khi đọc file {file_path.name}. Bỏ qua. Chi tiết: {e}")

    if not all_seasons_dfs:
        print("Không có dữ liệu để xử lý. Kết thúc.")
        return

    combined_df = pd.concat(all_seasons_dfs, ignore_index=True, sort=False)
    print(f"\nĐã hợp nhất dữ liệu thành công.")
    print(f"DataFrame tổng hợp có {len(combined_df)} dòng và {len(combined_df.columns)} cột.")

    # --- LƯU KẾT QUẢ ---
    output_filename = "01_combined_seasons.csv"
    output_path = PROCESSED_DATA_DIR / output_filename
    
    combined_df.to_csv(output_path, index=False)
    
    print("\n--- QUÁ TRÌNH HOÀN TẤT! ---")
    print(f"Dữ liệu thô đã được hợp nhất và lưu tại: {output_path}")
    print("Các cột đầu tiên của file kết quả:")
    print(combined_df.head().iloc[:, :5]) # In ra 5 cột đầu tiên của 5 dòng đầu

if __name__ == "__main__":
    main()