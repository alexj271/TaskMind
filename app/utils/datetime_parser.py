from datetime import datetime
from zoneinfo import ZoneInfo
from tortoise import models
from app.core.config import get_settings
from app.models.city import City

# Словарь городов -> timezone (резервный, если БД недоступна)
CITY_TIMEZONE_MAP = {
    "Moscow": "Europe/Moscow",
    "New York": "America/New_York",
    "London": "Europe/London",
    "Tokyo": "Asia/Tokyo",
    "San Francisco": "America/Los_Angeles",
    "Berlin": "Europe/Berlin",
    # Добавить больше по необходимости
}

class AmbiguousCityError(Exception):
    """Исключение для случаев, когда найдено несколько городов с одним названием"""
    def __init__(self, city_name: str, cities_info: list):
        self.city_name = city_name
        self.cities_info = cities_info
        message = f"Найдено {len(cities_info)} городов с названием '{city_name}':\n"
        for info in cities_info:
            message += f"- {info['name']}, {info['country_code']} (timezone: {info['timezone']})\n"
        message += "Пожалуйста, укажите страну для точного определения."
        super().__init__(message)


async def detect_timezone(city: str = None, country: str = None, current_time: str = None, timezone_str: str = None) -> str | None:
    """
    Определяет часовой пояс в формате UTC+X на основе города, текущего времени или строки timezone.
    
    Args:
        city: Название города
        country: Код страны (ISO 2-буквенный) для точного определения города
        current_time: Текущее время в формате HH:MM
        timezone_str: Строка часового пояса (IANA или UTC+X)
    
    Returns:
        Часовой пояс в формате UTC+X или None если не удалось определить
        
    Raises:
        AmbiguousCityError: Если найдено несколько городов с одним названием и не указана страна
    """
    if not any([city, current_time, timezone_str]):
        return None
    
    detected_tz = None
    
    # 1. Если дан timezone_str, используем его
    if timezone_str:
        try:
            # Если уже в формате UTC+X, возвращаем
            if timezone_str.startswith("UTC"):
                return timezone_str
            # Иначе пытаемся создать ZoneInfo
            tz = ZoneInfo(timezone_str)
            detected_tz = timezone_str
        except:
            pass
    
    # 2. Если дан city, ищем timezone
    if city and not detected_tz:
        # Сначала пытаемся найти в БД
        try:
            # Ищем по основному имени или альтернативным названиям
            query = models.Q(name__iexact=city.strip()) | models.Q(alternatenames__icontains=city.strip())
            
            # Если указана страна, добавляем фильтр
            if country:
                query &= models.Q(country_code__iexact=country.strip())
            
            cities = await City.filter(query).all()
            
            if len(cities) == 0:
                # Город не найден в БД, используем словарь
                detected_tz = CITY_TIMEZONE_MAP.get(city.strip().title())
            elif len(cities) == 1:
                # Найден один город
                city_obj = cities[0]
                if city_obj.timezone:
                    detected_tz = city_obj.timezone
            else:
                # Найдено несколько городов с одним названием
                if not country:
                    # Если страна не указана, возвращаем ошибку с информацией о найденных городах
                    cities_info = [
                        {
                            'name': city_obj.name,
                            'country_code': city_obj.country_code,
                            'timezone': city_obj.timezone
                        }
                        for city_obj in cities
                    ]
                    raise AmbiguousCityError(city.strip(), cities_info)
                # Если страна указана, но всё ещё несколько результатов, берём первый
                city_obj = cities[0]
                if city_obj.timezone:
                    detected_tz = city_obj.timezone
        except AmbiguousCityError:
            # Перебрасываем исключение выше
            raise
        except:
            # Если БД недоступна, используем словарь
            detected_tz = CITY_TIMEZONE_MAP.get(city.strip().title())
    
    # 3. Если дан current_time, вычисляем offset от UTC
    if current_time and not detected_tz:
        try:
            # Парсим время
            time_parts = current_time.split(":")
            if len(time_parts) == 2:
                user_hour = int(time_parts[0])
                user_minute = int(time_parts[1])
                
                # Текущее UTC время
                utc_now = datetime.now(ZoneInfo("UTC"))
                utc_hour = utc_now.hour
                utc_minute = utc_now.minute
                
                # Вычисляем offset в часах
                offset_hours = user_hour - utc_hour
                # Корректируем если переход через сутки
                if offset_hours > 12:
                    offset_hours -= 24
                elif offset_hours < -12:
                    offset_hours += 24
                
                # Округляем до ближайшего часа (упрощение)
                offset_hours = round(offset_hours)
                
                detected_tz = f"UTC{offset_hours:+d}"
        except:
            pass
    
    # Если нашли timezone, конвертируем в UTC+X
    if detected_tz:
        try:
            if not detected_tz.startswith("UTC"):
                # Получаем offset
                dt = datetime.now(ZoneInfo(detected_tz))
                offset = dt.utcoffset()
                offset_hours = int(offset.total_seconds() / 3600)
                return f"UTC{offset_hours:+d}"
            else:
                return detected_tz
        except:
            pass
    
    return None


# TODO: replace with robust NLP date parsing (e.g. dateparser with tz)

async def extract_datetime(text: str) -> datetime | None:
    # Placeholder: always None
    return None

async def now_utc() -> datetime:
    settings = get_settings()
    return datetime.now(tz=ZoneInfo(settings.timezone))
