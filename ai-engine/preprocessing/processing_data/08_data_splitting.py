import pandas as pd
import json
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent 
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
PROCESSED_DATA_DIR.mkdir(exist_ok=True)

INPUT_FILENAME = "final_dataset_for_modeling.csv"
INPUT_FILE_PATH = PROCESSED_DATA_DIR / INPUT_FILENAME

def main():
    """
    Chia bộ dữ liệu đã có đầy đủ đặc trưng thành các tập train, validation, test
    dựa trên các mùa giải.
    """
    print("--- SCRIPT 08: BẮT ĐẦU CHIA DỮ LIỆU (TRAIN/VAL/TEST) ---")
    
    try:
        df = pd.read_csv(INPUT_FILE_PATH, parse_dates=['Date'])
        # Đảm bảo dữ liệu được sắp xếp theo thời gian
        df = df.sort_values('Date').reset_index(drop=True)
        print(f"1. Đã đọc và sắp xếp thành công file '{INPUT_FILENAME}'.")
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file '{INPUT_FILE_PATH}'.")
        return

    # --- Định nghĩa các mùa giải cho từng tập ---
    # Lấy danh sách các mùa giải duy nhất, đã sắp xếp
    seasons = sorted(df['Season'].unique())
    
    if len(seasons) < 13:
        print("Cảnh báo: Dữ liệu không đủ 13 mùa giải như dự kiến. Điều chỉnh lại logic chia.")
        # Logic dự phòng nếu dữ liệu ít hơn
        test_seasons = seasons[-1:]
        val_seasons = seasons[-3:-1]
        train_seasons = seasons[:-3]
    else:
        # Logic chia chuẩn như backlog
        test_seasons = ['2023_24']
        val_seasons = ['2021_22', '2022_23']
        train_seasons = [s for s in seasons if s not in val_seasons + test_seasons]

    # --- Thực hiện chia dữ liệu ---
    train_df = df[df['Season'].isin(train_seasons)]
    val_df = df[df['Season'].isin(val_seasons)]
    test_df = df[df['Season'].isin(test_seasons)]
    
    print("\n2. Đã chia dữ liệu thành công:")
    print(f"   - Tập Train: {len(train_df)} dòng (Mùa giải từ {train_seasons[0]} đến {train_seasons[-1]})")
    print(f"   - Tập Validation: {len(val_df)} dòng (Mùa giải {val_seasons[0]} và {val_seasons[1]})")
    print(f"   - Tập Test: {len(test_df)} dòng (Mùa giải {test_seasons[0]})")
    
    # --- Lưu các file dữ liệu ---
    train_df.to_csv(PROCESSED_DATA_DIR / "train_data.csv", index=False)
    val_df.to_csv(PROCESSED_DATA_DIR / "val_data.csv", index=False)
    test_df.to_csv(PROCESSED_DATA_DIR / "test_data.csv", index=False)
    print("\n3. Đã lưu 3 file train_data.csv, val_data.csv, test_data.csv.")

    # --- Lưu thông tin về việc chia ---
    split_info = {
        "train": {"seasons": train_seasons, "matches": len(train_df)},
        "validation": {"seasons": val_seasons, "matches": len(val_df)},
        "test": {"seasons": test_seasons, "matches": len(test_df)}
    }
    
    with open(PROCESSED_DATA_DIR / "split_info.json", 'w') as f:
        json.dump(split_info, f, indent=4)
    print("4. Đã lưu thông tin chi tiết vào split_info.json.")
    
    print("\n--- HOÀN TẤT ---")

if __name__ == "__main__":
    main()