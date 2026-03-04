from app.db import test_connection

if __name__ == "__main__":
    ok = test_connection()
    print("DB OK" if ok else "DB FAILED")
