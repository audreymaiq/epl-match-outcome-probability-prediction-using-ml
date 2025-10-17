"""
Dùng mô hình Logistic Regression
"""

import pandas as pd
import joblib
import json
from pathlib import Path
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# --- CẤU HÌNH ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"
BEST_MODEL_DIR = MODEL_DIR / "best_models"
BEST_MODEL_DIR.mkdir(parents=True, exist_ok=True)

COLS_TO_DROP_FOR_TRAINING = [
    'Date', 'HomeTeam', 'AwayTeam', 'Season', 'FTR', 'FTHG', 'FTAG'
]

def prepare_data(df, target_col='FTR'):
    X = df.drop(columns=COLS_TO_DROP_FOR_TRAINING, errors='ignore')
    y = df[target_col]
    return X, y

def main():
    print("--- BẮT ĐẦU TINH CHỈNH THAM SỐ CHO LOGISTIC REGRESSION ---")
    
    # 1. Đọc và kết hợp dữ liệu
    try:
        train_df = pd.read_csv(PROCESSED_DATA_DIR / "train_data_v2.csv", parse_dates=['Date'])
        val_df = pd.read_csv(PROCESSED_DATA_DIR / "val_data_v2.csv", parse_dates=['Date'])
        tuning_df = pd.concat([train_df, val_df], ignore_index=True).sort_values('Date')
        print("1. Đã kết hợp dữ liệu train và validation để tuning.")
    except FileNotFoundError as e:
        print(f"Lỗi: không tìm thấy file. Vui lòng chạy script 09 trước. {e}")
        return

    # 2. Chuẩn bị dữ liệu
    X_tuning, y_tuning_raw = prepare_data(tuning_df)
    
    try:
        le = joblib.load(MODEL_DIR / "baseline_models_v2" / "label_encoder.pkl")
        y_tuning = le.transform(y_tuning_raw)
        print("2. Đã chuẩn bị dữ liệu và tải LabelEncoder.")
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy label_encoder.pkl. Vui lòng chạy script 09 trước.")
        return

    # 3. Thiết lập chiến lược Cross-Validation theo thời gian
    n_samples = len(X_tuning)
    time_series_cv = TimeSeriesSplit(n_splits=5, test_size=n_samples // 6) 
    print("3. Đã thiết lập TimeSeriesSplit Cross-Validation.")

    # 4. Tạo Pipeline bao gồm Scaling và Model
    # Đây là bước quan trọng để đảm bảo scaler được fit đúng trên từng fold của CV
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('model', LogisticRegression(max_iter=2000, random_state=42))
    ])
    print("4. Đã tạo Pipeline với StandardScaler và LogisticRegression.")

    # 5. Thiết lập không gian tham số cho GridSearchCV
    # 'model__C' - cú pháp để truy cập tham số C của bước 'model' trong pipeline
    param_grid = {
        'model__C': [0.001, 0.01, 0.1, 1, 10, 100],
        'model__solver': ['lbfgs', 'liblinear']
    }

    # 6. Chạy GridSearchCV
    print("\n--- 5. Bắt đầu quá trình tìm kiếm tham số... ---")
    grid_search = GridSearchCV(
        estimator=pipeline,
        param_grid=param_grid,
        scoring='neg_log_loss',
        cv=time_series_cv,
        verbose=1,
        n_jobs=-1
    )
    
    grid_search.fit(X_tuning, y_tuning)

    # 7. Lưu kết quả
    print("\n--- 6. Hoàn tất tuning ---")
    print(f"Điểm Log Loss tốt nhất: {-grid_search.best_score_:.4f}")
    print("Bộ tham số tốt nhất:")
    print(grid_search.best_params_)
    
    # Chuyển đổi best_params để dễ lưu hơn
    # Bỏ tiền tố 'model__'
    best_params_to_save = {k.split('__')[1]: v for k, v in grid_search.best_params_.items()}

    with open(BEST_MODEL_DIR / "best_lr_params_v2.json", 'w') as f:
        json.dump(best_params_to_save, f, indent=4)
    print(f"Đã lưu bộ tham số tại: {BEST_MODEL_DIR / 'best_lr_params_v2.json'}")

    # Lưu pipeline tốt nhất (bao gồm cả scaler đã được huấn luyện trên toàn bộ dữ liệu tuning)
    best_pipeline = grid_search.best_estimator_
    joblib.dump(best_pipeline, BEST_MODEL_DIR / "best_lr_pipeline_v2.pkl")
    print(f"Đã lưu pipeline tốt nhất tại: {BEST_MODEL_DIR / 'best_lr_pipeline_v2.pkl'}")
    
    print("\n--- HOÀN TẤT ---")

if __name__ == "__main__":
    main()