import pandas as pd
from pathlib import Path

# --- CẤU HÌNH ---
# Xác định đường dẫn tương đối để script chạy được ở mọi nơi
BASE_DIR = Path(__file__).resolve().parent  # Thư mục chứa file Python này
DATA_DIR = BASE_DIR / "raw" # Thư mục chứa các file CSV thô
REPORTS_DIR = BASE_DIR / "report" # Thư mục để lưu báo cáo

# Tự động tạo thư mục 'reports' nếu chưa có
REPORTS_DIR.mkdir(exist_ok=True)

def analyze_missing_values(file_paths, output_path):
    """
    Phân tích mô hình dữ liệu thiếu trên tập các file CSV.
    - Tính toán số lượng và % thiếu cho từng cột trong mỗi file.
    - Lưu kết quả tổng hợp vào một file CSV.

    Args:
        file_paths (list): Danh sách đường dẫn đến các file CSV.
        output_path (Path): Đường dẫn để lưu file báo cáo CSV.
    """
    print("--- Bắt đầu phân tích dữ liệu thiếu ---")
    
    all_missing_data = []

    for file_path in file_paths:
        # Lấy tên mùa giải từ tên file, ví dụ: '2011-12' -> '2011-12'
        season = file_path.stem
        
        try:
            df = pd.read_csv(file_path, low_memory=False)
        except Exception as e:
            print(f"Lỗi khi đọc file {file_path.name}: {e}. Bỏ qua file này.")
            continue
            
        total_rows = len(df)
        if total_rows == 0:
            print(f"Cảnh báo: File {file_path.name} rỗng. Bỏ qua.")
            continue

        missing_counts = df.isnull().sum()
        missing_percentages = (missing_counts / total_rows) * 100

        for col_name, count in missing_counts.items():
            # Chỉ ghi lại những cột có giá trị thiếu để báo cáo gọn gàng hơn
            if count > 0:
                all_missing_data.append({
                    "Season": season,
                    "Column_Name": col_name,
                    "Missing_Count": count,
                    "Missing_Percentage": round(missing_percentages[col_name], 2)
                })

    if not all_missing_data:
        print("Tuyệt vời! Không tìm thấy giá trị thiếu nào trong tất cả các file.")
        return

    # Tạo DataFrame từ danh sách các dictionary và lưu vào CSV
    report_df = pd.DataFrame(all_missing_data)
    # Sắp xếp để dễ theo dõi một cột qua các mùa
    report_df = report_df.sort_values(by=["Column_Name", "Season"])
    
    report_df.to_csv(output_path, index=False, encoding='utf-8')
    
    print(f"--- Hoàn thành Task 1.2: Báo cáo đã được lưu tại '{output_path}' ---")


if __name__ == "__main__":
    try:
        # Lấy danh sách file và sắp xếp theo tên để đảm bảo thứ tự thời gian
        csv_files = sorted(list(DATA_DIR.glob("*.csv")))
        if not csv_files:
            raise FileNotFoundError(f"Không tìm thấy file CSV nào trong thư mục: {DATA_DIR}")
            
        output_file_path = REPORTS_DIR / "missing_values_report.csv"
        
        analyze_missing_values(csv_files, output_file_path)

    except FileNotFoundError as e:
        print(f"Lỗi: {e}")
        print("Vui lòng đảm bảo thư mục 'data' tồn tại và chứa các file CSV của bạn.")