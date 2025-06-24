import os

def write_directory_structure(root_dir, output_file, ignore_dirs=None):
    if ignore_dirs is None:
        ignore_dirs = set()

    with open(output_file, 'w', encoding='utf-8') as f:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Bỏ qua thư mục nằm trong danh sách ignore
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]

            level = dirpath.replace(root_dir, '').count(os.sep)
            indent = ' ' * 4 * level
            f.write(f"{indent}{os.path.basename(dirpath)}/\n")

            subindent = ' ' * 4 * (level + 1)
            for filename in filenames:
                f.write(f"{subindent}{filename}\n")

# 🔧 Cấu hình đường dẫn và thư mục cần bỏ qua
root_directory = r'T:\github\Premier-League-Match-Outcome-Probability-Prediction-Using-Machine-Learning\ai-engine'
output_path = 'output.txt'          # File để ghi kết quả
ignore_folders = {'venv', '__pycache__'}  # Thư mục sẽ bị bỏ qua

write_directory_structure(root_directory, output_path, ignore_dirs=ignore_folders)
print(f"Đã ghi cấu trúc thư mục (bỏ qua {ignore_folders}) vào: {output_path}")
