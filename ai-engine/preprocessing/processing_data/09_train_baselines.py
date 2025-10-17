"""
Mục tiêu đầu tiên là trả lời câu hỏi: "Với bộ đặc trưng hiện tại, hiệu suất tối thiểu mà chúng ta có thể đạt được là bao nhiêu?"
Script này sẽ huấn luyện các mô hình cơ bản như Logistic Regression, Random Forest, XGBoost và LightGBM trên tập dữ liệu đã được xử lý.
=> Lựa chọn mô hình để Tinh chỉnh (Hyperparameter Tuning).
"""

import pandas as pd
import joblib
from pathlib import Path
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, log_loss
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

# --- CẤU HÌNH ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models" / "baseline_models_v2"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Các cột cần loại bỏ trước khi huấn luyện
COLS_TO_DROP_FOR_TRAINING = [
    'Date', 'HomeTeam', 'AwayTeam', 'Season', 
    'FTR', 'FTHG', 'FTAG'
]

def prepare_data(df, target_col='FTR'):
    """Tách X và y, đảm bảo các cột không mong muốn đã được loại bỏ."""
    X = df.drop(columns=COLS_TO_DROP_FOR_TRAINING, errors='ignore')
    y = df[target_col]
    return X, y

def main():
    print("--- BẮT ĐẦU HUẤN LUYỆN CÁC MÔ HÌNH CƠ BẢN ---")
    
    # 1. Đọc dữ liệu
    try:
        train_df = pd.read_csv(PROCESSED_DATA_DIR / "train_data_v2.csv", parse_dates=['Date'])
        val_df = pd.read_csv(PROCESSED_DATA_DIR / "val_data_v2.csv", parse_dates=['Date'])
        print("1. Đã đọc thành công dữ liệu train và validation.")
    except FileNotFoundError as e:
        print(f"Lỗi: không tìm thấy file dữ liệu. Vui lòng chạy script 08 trước. Chi tiết: {e}")
        return

    # 2. Chuẩn bị dữ liệu
    X_train, y_train_raw = prepare_data(train_df)
    X_val, y_val_raw = prepare_data(val_df)
    
    # Mã hóa nhãn (target)
    le = LabelEncoder()
    y_train = le.fit_transform(y_train_raw)
    y_val = le.transform(y_val_raw)
    print(f"2. Đã chuẩn bị dữ liệu và mã hóa nhãn. Các lớp: {le.classes_}")

    # 3. Định nghĩa các mô hình
    models = {
        'LogisticRegression': LogisticRegression(max_iter=1000, random_state=42),
        'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42),
        'XGBoost': XGBClassifier(eval_metric='mlogloss', random_state=42, n_jobs=-1),
        # Thêm verbose=-1 để ẩn thông báo không cần thiết
        'LightGBM': LGBMClassifier(random_state=42, n_jobs=-1, verbose=-1)
    }

    # Tạo một DataFrame để lưu kết quả
    results = []

    print("\n--- 3. Bắt đầu huấn luyện và đánh giá ---")
    for name, model in models.items():
        print(f"\nTraining model: {name}...")
        
        # Huấn luyện
        model.fit(X_train, y_train)
        
        # Đánh giá trên tập validation
        y_pred_proba = model.predict_proba(X_val)
        y_pred = model.predict(X_val) # Dự đoán lớp để tính accuracy

        accuracy = accuracy_score(y_val, y_pred)
        loss = log_loss(y_val, y_pred_proba)
        
        print(f"   -> Validation Accuracy: {accuracy:.4f}")
        print(f"   -> Validation Log Loss: {loss:.4f}")

        # Thêm kết quả vào danh sách
        results.append({
            'Model': name,
            'Accuracy': accuracy,
            'LogLoss': loss
        })
        
        # Lưu mô hình
        joblib.dump(model, MODEL_DIR / f"{name}.pkl")
        print(f"   -> Đã lưu mô hình tại: {MODEL_DIR / f'{name}.pkl'}")
        
    #  In ra bảng so sánh kết quả cuối cùng
    results_df = pd.DataFrame(results).sort_values(by='LogLoss', ascending=True).reset_index(drop=True)
    print("\n--- 4. Bảng tổng kết hiệu suất các mô hình cơ bản ---")
    print(results_df)

    # Lưu cả LabelEncoder để sử dụng sau này
    joblib.dump(le, MODEL_DIR / "label_encoder.pkl")
    print("\nĐã lưu LabelEncoder.")
    
    print("\n--- HOÀN TẤT ---")
    print("Gợi ý: Dựa trên kết quả Log Loss, chọn 1-2 mô hình tốt nhất để tinh chỉnh ở bước tiếp theo.")

if __name__ == "__main__":
    main()