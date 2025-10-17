import pandas as pd
import joblib
import json
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (
    accuracy_score, 
    log_loss, 
    classification_report, 
    confusion_matrix
)

# --- CẤU HÌNH ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"
BEST_MODEL_DIR = MODEL_DIR / "best_models"
REPORTS_DIR = BASE_DIR / "preprocessing" / "output"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Các cột cần loại bỏ trước khi đưa vào mô hình
COLS_TO_DROP_FOR_PREDICTION = [
    'Date', 'HomeTeam', 'AwayTeam', 'Season', 
    'FTR', 'FTHG', 'FTAG'
]

def plot_confusion_matrix(cm, classes, title='Ma trận nhầm lẫn', cmap=plt.cm.Blues):
    """Vẽ và lưu ma trận nhầm lẫn."""
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap=cmap, 
                xticklabels=classes, yticklabels=classes)
    plt.title(title)
    plt.ylabel('Nhãn thực tế (True label)')
    plt.xlabel('Nhãn dự đoán (Predicted label)')
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / 'confusion_matrix.png')
    plt.close() # Đóng plot để không hiển thị tự động

def plot_feature_importance(model, feature_names, model_type='linear'):
    """Vẽ và lưu độ quan trọng của đặc trưng."""
    if model_type == 'linear':
        importances = np.abs(model.coef_[0])
    else:
        importances = model.feature_importances_
    
    feature_importance = pd.DataFrame({'feature': feature_names, 'importance': importances})
    feature_importance = feature_importance.sort_values('importance', ascending=False).head(20)
    
    plt.figure(figsize=(10, 8))
    sns.barplot(x='importance', y='feature', data=feature_importance)
    plt.title('Top 20 Đặc trưng quan trọng nhất')
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / 'feature_importance.png')
    plt.close() # Đóng plot để không hiển thị tự động

def main():
    print("--- SCRIPT 12: BẮT ĐẦU ĐÁNH GIÁ MÔ HÌNH CUỐI CÙNG TRÊN TẬP TEST ---")
    
    # 1. Tải các thành phần cần thiết
    try:
        print("1. Tải mô hình, dữ liệu test và label encoder...")
        pipeline = joblib.load(BEST_MODEL_DIR / "best_lr_pipeline_v2.pkl")
        test_df = pd.read_csv(PROCESSED_DATA_DIR / "test_data_v2.csv", parse_dates=['Date'])
        le = joblib.load(MODEL_DIR / "baseline_models_v2" / "label_encoder.pkl")
        print("   -> Tải thành công.")
    except FileNotFoundError as e:
        print(f"LỖI: Không tìm thấy file cần thiết. Vui lòng chạy các script trước. Chi tiết: {e}")
        return

    # 2. Chuẩn bị dữ liệu test
    X_test = test_df.drop(columns=COLS_TO_DROP_FOR_PREDICTION, errors='ignore')
    y_test_raw = test_df['FTR']
    y_test = le.transform(y_test_raw)
    class_names = le.classes_
    print("\n2. Đã chuẩn bị dữ liệu test.")

    # 3. Thực hiện dự đoán
    y_pred_proba = pipeline.predict_proba(X_test)
    y_pred_encoded = pipeline.predict(X_test)
    y_pred_labels = le.inverse_transform(y_pred_encoded) # Dịch ngược dự đoán số về chữ
    print("3. Đã thực hiện dự đoán trên tập test.")

    # 4. Tính toán và lưu các chỉ số đánh giá
    print("\n--- 4. Kết quả đánh giá trên tập Test ---")
    accuracy = accuracy_score(y_test, y_pred_encoded)
    loss = log_loss(y_test, y_pred_proba)
    report_text = classification_report(y_test, y_pred_encoded, target_names=class_names)
    report_dict = classification_report(y_test, y_pred_encoded, target_names=class_names, output_dict=True)
    
    print(f"   -> Accuracy: {accuracy:.4f}")
    print(f"   -> Log Loss: {loss:.4f}")
    print("\nBáo cáo chi tiết (Classification Report):\n", report_text)
    # ... (Lưu báo cáo JSON) ...
    final_evaluation = {'model_name': 'best_lr_pipeline_v2.pkl', 'accuracy': accuracy, 'log_loss': loss, 'classification_report': report_dict}
    with open(REPORTS_DIR / "final_evaluation_report_v2.json", 'w') as f: json.dump(final_evaluation, f, indent=4)
    print("   -> Báo cáo đánh giá đã được lưu vào file JSON.")
    
    # 5. Phân tích Ma trận nhầm lẫn
    print("\n5. Tạo Ma trận nhầm lẫn...")
    cm = confusion_matrix(y_test, y_pred_encoded)
    plot_confusion_matrix(cm, classes=class_names)
    print("   -> Biểu đồ Ma trận nhầm lẫn đã được lưu.")

    # 6. Phân tích Độ quan trọng của đặc trưng
    print("\n6. Phân tích Độ quan trọng của đặc trưng...")
    logistic_regression_model = pipeline.named_steps['model']
    feature_names = X_test.columns
    plot_feature_importance(logistic_regression_model, feature_names, model_type='linear')
    print("   -> Biểu đồ Độ quan trọng của đặc trưng đã được lưu.")

    # --- BƯỚC MỚI: 7. TẠO VÀ LƯU BÁO CÁO PHÂN TÍCH DỰ ĐOÁN CHI TIẾT ---
    print("\n7. Tạo file phân tích chi tiết cho từng dự đoán...")
    
    # Tạo một DataFrame mới để chứa kết quả phân tích
    analysis_df = test_df[['Date', 'HomeTeam', 'AwayTeam', 'FTR']].copy()
    
    # Thêm cột dự đoán (đã được dịch ngược về 'H', 'D', 'A')
    analysis_df['Predicted_FTR'] = y_pred_labels
    
    # Thêm các cột xác suất cho từng kết quả
    # Lấy tên lớp từ label encoder để đảm bảo đúng thứ tự
    for i, class_name in enumerate(class_names):
        analysis_df[f'Prob_{class_name}'] = y_pred_proba[:, i]
        
    # Thêm cột kiểm tra xem dự đoán có đúng không
    analysis_df['Is_Correct'] = (analysis_df['FTR'] == analysis_df['Predicted_FTR']).astype(int)
    
    # Lưu file phân tích
    analysis_output_path = REPORTS_DIR / "prediction_analysis_v2.csv"
    analysis_df.to_csv(analysis_output_path, index=False)
    
    print(f"   -> Đã lưu file phân tích chi tiết tại: '{analysis_output_path}'")
    
    print("\n--- HOÀN TẤT ---")

if __name__ == "__main__":
    main()