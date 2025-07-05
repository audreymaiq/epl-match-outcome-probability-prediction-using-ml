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
    4. Chuẩn hóa cột Date và sắp xếp dữ liệu.
    5. Lưu kết quả ra file mới.
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
            # =================================================================
            # === THAY ĐỔI QUAN TRỌNG NHẤT ĐỂ SỬA LỖI BOM ===
            # Sử dụng encoding='utf-8-sig' để Pandas tự động phát hiện và loại bỏ BOM
            df = pd.read_csv(file_path, low_memory=False, encoding='utf-8-sig')
            # =================================================================
            
            # Bước dọn dẹp khoảng trắng vẫn nên giữ lại để phòng ngừa
            df.columns = [col.strip() for col in df.columns]

            season_name = file_path.stem.replace('season_', '')
            
            if 'Div' in df.columns:
                df.insert(1, 'Season', season_name)
            else:
                df.insert(0, 'Season', season_name)
            
            all_seasons_dfs.append(df)
            
        except Exception as e:
            print(f"  - LỖI khi đọc file {file_path.name}. Bỏ qua. Chi tiết: {e}")

    if not all_seasons_dfs:
        print("Không có dữ liệu để xử lý. Kết thúc.")
        return

    combined_df = pd.concat(all_seasons_dfs, ignore_index=True, sort=False)
    print(f"\nĐã hợp nhất dữ liệu thành công.")
    print(f"DataFrame tổng hợp có {len(combined_df)} dòng và {len(combined_df.columns)} cột.")

    print("\n--- Bắt đầu chuẩn hóa cột Date ---")
    if 'Date' in combined_df.columns:
        combined_df['Date'] = pd.to_datetime(combined_df['Date'], dayfirst=True, errors='coerce')
        rows_before_drop = len(combined_df)
        combined_df.dropna(subset=['Date'], inplace=True)
        rows_after_drop = len(combined_df)
        if rows_before_drop > rows_after_drop:
            print(f"Đã xóa {rows_before_drop - rows_after_drop} dòng có định dạng ngày không hợp lệ.")
        print("Đã chuẩn hóa cột 'Date' sang định dạng datetime.")
    else:
        print("CẢNH BÁO: Không tìm thấy cột 'Date' để chuẩn hóa.")

    print("\n--- Bắt đầu sắp xếp dữ liệu ---")
    if 'Date' in combined_df.columns:
        combined_df = combined_df.sort_values(by='Date').reset_index(drop=True)
        print("Đã sắp xếp toàn bộ dữ liệu theo ngày tháng.")
    else:
        print("CẢNH BÁO: Không thể sắp xếp vì không có cột 'Date'.")

    output_filename = "combined_seasons.csv"
    output_path = PROCESSED_DATA_DIR / output_filename
    combined_df.to_csv(output_path, index=False)
    
    print("\n--- QUÁ TRÌNH HOÀN TẤT! ---")
    print(f"Dữ liệu đã được hợp nhất, chuẩn hóa và lưu tại: {output_path}")
    print("Các cột đầu tiên của file kết quả (đã sắp xếp):")
    print("--- 5 dòng đầu tiên (cũ nhất) ---")
    print(combined_df.head().iloc[:, :5])
    print("\n--- 5 dòng cuối cùng (mới nhất) ---")
    print(combined_df.tail().iloc[:, :5])


if __name__ == "__main__":
    main()