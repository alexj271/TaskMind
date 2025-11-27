from tortoise import Tortoise
import urllib.request
import zipfile
import csv
import os
import tempfile
import sys
import socket
from pathlib import Path
import shutil
from tqdm import tqdm

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# URL для скачивания
GEONAMES_URL = "https://download.geonames.org/export/dump/cities500.zip"
CSV_FILENAME = "cities500.txt"

# Минимальная популяция для импорта
MIN_POPULATION = 1000


def download_file(url: str, dest_path: str, chunk_size: int = 8192):
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": "https://download.geonames.org/export/dump/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Priority": "u=0, i",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

    # --- HEAD запрос ---
    try:
        req_head = urllib.request.Request(url, headers=headers, method="HEAD")
        with urllib.request.urlopen(req_head, timeout=10) as response:
            total_size = response.headers.get("Content-Length")
            total_size = int(total_size) if total_size else None
    except Exception:
        total_size = None

    # --- GET запрос ---
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        pbar = tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=dest.name,
        )

        with open(dest, "wb") as f:
            while True:
                try:
                    chunk = response.read(chunk_size)
                except socket.timeout:
                    print("⚠ read() timeout — повторяем чтение...")
                    continue

                if not chunk:
                    break

                f.write(chunk)
                pbar.update(len(chunk))

        pbar.close()

    print(f"✔ Файл скачан: {dest}")



async def import_cities(zip_path, data_dir):
    """Импорт городов из GeoNames в базу данных"""
    
    # Инициализация Tortoise
    from app.core.db import TORTOISE_ORM
    await Tortoise.init(config=TORTOISE_ORM)
    
    # Создание таблиц если не существуют
    await Tortoise.generate_schemas()
    
    from app.models.city import City

    csv_path = data_dir / CSV_FILENAME

    # Распаковка
    print("Распаковка...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extract(CSV_FILENAME, data_dir)
    
    print("Парсинг CSV и запись в БД...")
    
    imported_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        
        for row in reader:
            try:
                # Парсинг строки
                # geonameid, name, asciiname, alternatenames, latitude, longitude, 
                # feature_class, feature_code, country_code, cc2, admin1_code, 
                # admin2_code, admin3_code, admin4_code, population, elevation, 
                # dem, timezone, modification_date
                
                population = int(row[14]) if row[14] else 0
                
                print(row[1], population)
                city = City(
                    name=row[1],  # name
                    timezone=row[17] if row[17] else None,  # timezone
                    country_code=row[8] if row[8] else None,  # country_code
                    population=population,
                    latitude=float(row[4]),
                    longitude=float(row[5])
                )
                
                await city.save()
                imported_count += 1
                
                if imported_count % 1000 == 0:
                    print(f"Импортировано {imported_count} городов...")
            
            except Exception as e:
                print(f"Ошибка при обработке строки: {e}")
                continue
    
    print(f"Импорт завершен. Всего импортировано {imported_count} городов.")


if __name__ == "__main__":
    import asyncio
        
    # Создаем папку data относительно корня проекта
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    zip_path = data_dir / "cities500.zip"
    csv_path = data_dir / CSV_FILENAME
    
    print("Скачивание файла с городами...")
    
    # Скачивание с прогрессом и resume
    # download_file(GEONAMES_URL, zip_path)

    # Импорт городов в БД
    asyncio.run(import_cities(zip_path, data_dir))