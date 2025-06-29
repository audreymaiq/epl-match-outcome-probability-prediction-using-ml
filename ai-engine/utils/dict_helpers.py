# ai-engine/utils/dict_helpers.py

from typing import Any, Dict, List
import collections.abc

def get_nested_value(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Lấy giá trị từ một dictionary lồng nhau bằng cách sử dụng một chuỗi đường dẫn.
    
    Ví dụ:
        data = {'a': {'b': {'c': 1}}}
        get_nested_value(data, 'a.b.c')  # Trả về 1
        get_nested_value(data, 'a.x.y', default='not_found') # Trả về 'not_found'
        
    Args:
        data (Dict[str, Any]): Dictionary đầu vào.
        path (str): Chuỗi đường dẫn, các key được phân tách bằng dấu chấm.
        default (Any, optional): Giá trị mặc định nếu không tìm thấy đường dẫn. Defaults to None.
        
    Returns:
        Any: Giá trị tìm thấy hoặc giá trị mặc định.
    """
    if not isinstance(data, dict) or not isinstance(path, str):
        return default
        
    keys = path.split('.')
    current_level = data
    
    for key in keys:
        if isinstance(current_level, dict) and key in current_level:
            current_level = current_level[key]
        else:
            return default
            
    return current_level

def deep_merge_dicts(d1: Dict[str, Any], d2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gộp (merge) hai dictionary một cách đệ quy.
    
    Các giá trị từ d2 sẽ ghi đè lên các giá trị từ d1.
    Nếu cả hai giá trị ở cùng một key là dictionary, chúng sẽ được gộp đệ quy.
    
    Args:
        d1 (Dict[str, Any]): Dictionary gốc.
        d2 (Dict[str, Any]): Dictionary để gộp vào.
        
    Returns:
        Dict[str, Any]: Dictionary đã được gộp.
    """
    for key, value in d2.items():
        if key in d1 and isinstance(d1[key], dict) and isinstance(value, collections.abc.Mapping):
            # Nếu cả hai là dict, gộp đệ quy
            d1[key] = deep_merge_dicts(d1[key], value)
        else:
            # Ghi đè hoặc thêm mới
            d1[key] = value
            
    return d1