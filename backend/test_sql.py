import psycopg2
import sys

def test_connection():
    # 這裡直接寫死你 Docker 測試成功的參數
    params = {
        "dbname": "contexture",
        "user": "contexture_user",
        "password": "contexture_pass",
        "host": "127.0.0.1",
        "port": 5433
    }
    
    print(f"正在嘗試連線到: {params['host']}:{params['port']} ...")
    
    try:
        conn = psycopg2.connect(**params)
        print("✅ 連線成功！")
        
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print(f"資料庫版本: {version[0]}")
            
            cur.execute("SELECT current_database(), current_user;")
            db_info = cur.fetchone()
            print(f"當前資料庫: {db_info[0]}, 當前用戶: {db_info[1]}")
            
        conn.close()
        print("✅ 測試完成，連線已關閉。")
        
    except psycopg2.OperationalError as e:
        print("\n❌ 連線失敗 (OperationalError):")
        print(f"錯誤訊息: {e}")
        print("\n這代表雖然網路通了，但資料庫拒絕了你的帳密。")
        print("請確認 Windows 服務中是否關閉了本機的 PostgreSQL？")
        
    except Exception as e:
        print(f"\n❌ 發生其他錯誤: {e}")

if __name__ == "__main__":
    test_connection()
