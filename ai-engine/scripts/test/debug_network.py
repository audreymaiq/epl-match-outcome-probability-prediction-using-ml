# ai-engine\scripts\test\debug_network.py

import sys
from curl_cffi.requests import Session, RequestsError

# --- THÔNG TIN CẦN TEST ---
# URL để lấy danh sách các mùa giải của Premier League
TEST_URL = "https://api.sofascore.com/api/v1/unique-tournament/17/seasons"

# Giả lập header của một trình duyệt thật
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

# Giả lập trình duyệt Chrome 110
IMPERSONATE = "chrome110"

# --- SCRIPT TEST ---
def main():
    print("--- Starting Minimal Network Test ---")
    print(f"Target URL: {TEST_URL}")
    print(f"Impersonating: {IMPERSONATE}")
    
    session = None
    try:
        session = Session(impersonate=IMPERSONATE, verify=True)
        
        print("\nSending request...")
        response = session.get(TEST_URL, headers=HEADERS, timeout=30)
        
        print(f"Response Status Code: {response.status_code}")
        
        response.raise_for_status() # Báo lỗi nếu status code là 4xx hoặc 5xx
        
        print("\n✓✓✓ TEST SUCCESSFUL! ✓✓✓")
        print("Network connection to SofaScore is working correctly.")
        
        # In ra một phần dữ liệu để xác nhận
        data = response.json()
        print("\nSample Data Received:")
        if "seasons" in data and data["seasons"]:
            print(data["seasons"][0])
        else:
            print(data)
            
        return 0 # Mã thoát thành công

    except RequestsError as e:
        print("\n✗✗✗ TEST FAILED! ✗✗✗")
        print("A network error occurred. This is likely the root cause of the problem.")
        print("-" * 50)
        print(f"Error Type: {type(e)}")
        print(f"Error Message: {e}")
        print("-" * 50)
        # In traceback đầy đủ
        import traceback
        traceback.print_exc()
        return 1 # Mã thoát thất bại
        
    except Exception as e:
        print("\n✗✗✗ TEST FAILED WITH UNEXPECTED ERROR! ✗✗✗")
        print("-" * 50)
        print(f"Error Type: {type(e)}")
        print(f"Error Message: {e}")
        print("-" * 50)
        import traceback
        traceback.print_exc()
        return 1

    finally:
        if session:
            session.close()
            print("\nSession closed.")
        print("--- Test Finished ---")

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)