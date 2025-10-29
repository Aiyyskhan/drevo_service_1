import io, json, os, time, requests
from datetime import timedelta
from PIL import Image

API_URL = "http://localhost:8080/upload"

def upload(file_path: str):
    # Проверяем, что файл существует
    if not os.path.isfile(file_path):
        print(f"❌ Файл '{file_path}' не найден.")
        return
    
    # Проверяем, что это GIF
    if not file_path.lower().endswith(".gif"):
        print("❌ Можно загружать только GIF-файлы.")
        return
    
    # Загружаем файл
    filename = os.path.basename(file_path)
    file_stat = os.stat(file_path)

    with open(file_path, "rb") as f:
        files = {"file": (filename, f, "image/gif")}
        print(f"⏳ Загружаем '{filename}' ({file_stat.st_size} байт)...")
        response = requests.post(API_URL, files=files)

    print("⏳ Ожидаем ответ от сервера...")
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "ok":
            print(f"✅ Успешно загружено! URL: {data.get('url')}")
        else:
            print(f"❌ Ошибка загрузки: {data.get('detail')}")
    else:
        print(f"❌ Ошибка сервера: {response.status_code} - {response.text}")
