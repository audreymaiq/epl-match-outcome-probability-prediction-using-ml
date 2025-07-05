import pandas as pd
import glob
import os
from collections import Counter

# --- CẤU HÌNH ---
# Đường dẫn đến thư mục chứa các file CSV thô
RAW_DATA_DIR = 'C:\\Users\\aliza\\Premier-League-Match-Outcome-Probability-Prediction-Using-Machine-Learning\\ai-engine\\data\\raw'
# Tên file báo cáo đầu ra
OUTPUT_REPORT_FILE = "C:\\Users\\aliza\\Premier-League-Match-Outcome-Probability-Prediction-Using-Machine-Learning\\ai-engine\\data\\data_analysis.txt"

def analyze_schema():
    """
    Hàm chính để phân tích tính nhất quán của schema trên nhiều file CSV.
    """
    # Lấy danh sách tất cả các file CSV và sắp xếp chúng
    all_csv_files = sorted(glob.glob(os.path.join(RAW_DATA_DIR, "*.csv")))

    if not all_csv_files:
        print(f"Lỗi: Không tìm thấy file CSV nào trong thư mục '{RAW_DATA_DIR}'.")
        print("Vui lòng đảm bảo bạn đã đặt các file CSV vào đúng thư mục.")
        return

    report_content = []
    file_schemas = {}
    all_column_names = []

    print(f"Bắt đầu phân tích {len(all_csv_files)} file CSV...")

    # --- Vòng lặp 1: Thu thập thông tin từ mỗi file ---
    for file_path in all_csv_files:
        file_name = os.path.basename(file_path)
        try:
            # low_memory=False để tránh cảnh báo về kiểu dữ liệu hỗn hợp
            df = pd.read_csv(file_path, low_memory=False)
            
            # Lưu trữ thông tin schema
            file_schemas[file_name] = {
                'num_cols': len(df.columns),
                'columns': set(df.columns),
                'dtypes': df.dtypes
            }
            all_column_names.extend(list(df.columns))
            print(f"  - Đã đọc và phân tích file: {file_name}")

        except Exception as e:
            print(f"Lỗi khi đọc file {file_name}: {e}")
            continue
    
    # --- Phân tích tổng hợp sau khi thu thập ---
    
    # Tìm các cột chung cho tất cả các file
    if not file_schemas:
        print("Không có file nào được phân tích thành công. Dừng chương trình.")
        return
        
    common_columns = set.intersection(*[schema['columns'] for schema in file_schemas.values()])

    # --- Bắt đầu tạo báo cáo ---
    
    report_content.append("="*50)
    report_content.append(" BÁO CÁO PHÂN TÍCH TÍNH NHẤT QUÁN SCHEMA ")
    report_content.append("="*50 + "\n")
    
    # 1. Tóm tắt chung
    report_content.append("### 1. TÓM TẮT CHUNG ###")
    report_content.append(f"- Tổng số file đã phân tích: {len(file_schemas)}")
    report_content.append(f"- Tổng số cột chung (xuất hiện trong TẤT CẢ các file): {len(common_columns)}")
    report_content.append(f"- Các cột chung: {sorted(list(common_columns))}\n")

    # 2. Phân tích sự khác biệt về cột
    report_content.append("### 2. PHÂN TÍCH SỰ KHÁC BIỆT VỀ CỘT ###")
    for file_name, schema in file_schemas.items():
        unique_to_file = schema['columns'] - common_columns
        if unique_to_file:
            report_content.append(f"- File '{file_name}' có {len(unique_to_file)} cột bổ sung: {sorted(list(unique_to_file))}")
    report_content.append("\n")

    # 3. Phân tích chi tiết từng file
    report_content.append("### 3. PHÂN TÍCH CHI TIẾT TỪNG FILE ###")
    for file_name, schema in file_schemas.items():
        report_content.append("-" * 40)
        report_content.append(f"File: {file_name}")
        report_content.append(f"  - Số lượng cột: {schema['num_cols']}")
        report_content.append("  - Kiểu dữ liệu (Data Types):")
        report_content.append(schema['dtypes'].to_string())
        report_content.append("\n")

    # --- Lưu báo cáo vào file ---
    try:
        with open(OUTPUT_REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_content))
        print(f"\nThành công! Báo cáo đã được lưu tại: {OUTPUT_REPORT_FILE}")
    except Exception as e:
        print(f"Lỗi khi ghi file báo cáo: {e}")


if __name__ == "__main__":
    analyze_schema()