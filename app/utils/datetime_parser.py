from datetime import datetime
from zoneinfo import ZoneInfo
from tortoise import models
from tortoise.models import Q
from app.core.config import get_settings
from app.models.city import City

# Простая таблица транслитерации кириллица → латиница
CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh',
    'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
    'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts',
    'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
}

def transliterate_cyrillic_to_latin(text: str) -> str:
    """Простая транслитерация кириллицы в латиницу"""
    result = ""
    for char in text:
        result += CYRILLIC_TO_LATIN.get(char, char)
    return result

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
            city_clean = city.strip()
            
            # Подготовим варианты для поиска
            search_variants = [city_clean, city_clean.lower(), city_clean.title()]
            
            # Если есть кириллица, добавляем транслитерированные варианты
            if any(ord(c) >= 1040 and ord(c) <= 1103 for c in city_clean):  # Проверка на кириллицу
                transliterated = transliterate_cyrillic_to_latin(city_clean)
                search_variants.extend([transliterated, transliterated.lower(), transliterated.title()])
            
            # Создаем несколько вариантов поиска для лучшего покрытия
            search_queries = []
            for variant in search_variants:
                search_queries.extend([
                    # Точное совпадение по имени
                    Q(name__iexact=variant),
                    # Поиск в альтернативных названиях (точное в списке)
                    Q(alternatenames__icontains=f",{variant},"),
                    Q(alternatenames__icontains=f"{variant},"),
                    Q(alternatenames__icontains=f",{variant}"),
                    # Поиск содержащий (для частичных совпадений)
                    Q(name__icontains=variant),
                    # Поиск в альтернативных названиях содержащий
                    Q(alternatenames__icontains=variant),
                ])
            
            # Объединяем все поиски
            combined_query = search_queries[0]
            for q in search_queries[1:]:
                combined_query |= q
            
            # Если указана страна, добавляем фильтр
            if country:
                combined_query &= Q(country_code__iexact=country.strip())
            
            cities = await City.filter(combined_query).all()
            
            # Убираем дубликаты по ID
            unique_cities = {city.id: city for city in cities}.values()
            cities = list(unique_cities)
            
            if len(cities) == 0:
                # Город не найден в БД, используем словарь
                detected_tz = CITY_TIMEZONE_MAP.get(city.strip().title())
            elif len(cities) == 1:
                # Найден один город
                city_obj = cities[0]
                if city_obj.timezone:
                    detected_tz = city_obj.timezone
            else:
                # Найдено несколько городов - применяем умную логику выбора
                if not country:
                    # Сортируем города по релевантности
                    scored_cities = []
                    for city_obj in cities:
                        score = 0
                        city_name_lower = city_obj.name.lower()
                        search_lower = city_clean.lower()
                        
                        # Подготовим варианты поиска включая транслитерацию
                        search_variants = [search_lower]
                        if any(ord(c) >= 1040 and ord(c) <= 1103 for c in city_clean):  # Если есть кириллица
                            transliterated = transliterate_cyrillic_to_latin(city_clean).lower()
                            search_variants.append(transliterated)
                        
                        max_score = 0
                        for search_variant in search_variants:
                            variant_score = 0
                            
                            # Точное совпадение имени - максимальный приоритет
                            if city_name_lower == search_variant:
                                variant_score += 100
                            # Имя начинается с искомого и длина схожая - очень высокий приоритет  
                            elif city_name_lower.startswith(search_variant) and len(city_obj.name) <= len(search_variant) + 3:
                                variant_score += 50
                            # Имя начинается с искомого - высокий приоритет
                            elif city_name_lower.startswith(search_variant):
                                variant_score += 20
                            # Искомое слово является полным словом в названии
                            elif f" {search_variant} " in f" {city_name_lower} " or city_name_lower.endswith(f" {search_variant}") or city_name_lower.startswith(f"{search_variant} "):
                                variant_score += 15
                            # Содержится в имени - средний приоритет
                            elif search_variant in city_name_lower:
                                # Штраф за длинные названия (вероятно не то что ищем)
                                if len(city_obj.name) > len(search_variant) * 2:
                                    variant_score += 1
                                else:
                                    variant_score += 8
                            # Содержится в альтернативных названиях
                            elif city_obj.alternatenames:
                                alt_names_lower = city_obj.alternatenames.lower()
                                # Точное совпадение в альтернативных названиях
                                if f",{search_variant}," in f",{alt_names_lower}," or alt_names_lower.startswith(f"{search_variant},") or alt_names_lower.endswith(f",{search_variant}"):
                                    variant_score += 30
                                # Содержится в альтернативных названиях
                                elif search_variant in alt_names_lower:
                                    variant_score += 5
                            
                            max_score = max(max_score, variant_score)
                        
                        score = max_score
                            
                        # Приоритет для стран где пользователь вероятнее всего находится
                        if city_obj.country_code in ['RU', 'US', 'GB', 'DE', 'FR', 'CA', 'AU']:
                            score += 10
                        # Дополнительный приоритет для России (предполагаем русскоязычного пользователя)
                        if city_obj.country_code == 'RU':
                            score += 5
                            
                        scored_cities.append((score, city_obj))
                    
                    # Сортируем по убыванию score
                    scored_cities.sort(key=lambda x: x[0], reverse=True)
                    
                    # Если есть явный лидер по score (разница > 10), используем его
                    if len(scored_cities) > 1 and scored_cities[0][0] > scored_cities[1][0] + 10:
                        city_obj = scored_cities[0][1]
                        if city_obj.timezone:
                            detected_tz = city_obj.timezone
                    # Если топ результат имеет очень высокий score (100+), используем его даже без большой разницы
                    elif len(scored_cities) > 0 and scored_cities[0][0] >= 100:
                        city_obj = scored_cities[0][1] 
                        if city_obj.timezone:
                            detected_tz = city_obj.timezone
                    else:
                        # Если нет явного лидера, возвращаем ошибку с информацией о найденных городах
                        cities_info = [
                            {
                                'name': city_obj.name,
                                'country_code': city_obj.country_code,
                                'timezone': city_obj.timezone,
                                'score': score
                            }
                            for score, city_obj in scored_cities[:10]  # Показываем только топ 10
                        ]
                        raise AmbiguousCityError(city.strip(), cities_info)
                else:
                    # Если страна указана, все еще применяем scoring для выбора лучшего варианта
                    scored_cities = []
                    for city_obj in cities:
                        score = 0
                        city_name_lower = city_obj.name.lower()
                        search_lower = city_clean.lower()
                        
                        # Подготовим варианты поиска включая транслитерацию
                        search_variants = [search_lower]
                        if any(ord(c) >= 1040 and ord(c) <= 1103 for c in city_clean):  # Если есть кириллица
                            transliterated = transliterate_cyrillic_to_latin(city_clean).lower()
                            search_variants.append(transliterated)
                        
                        max_score = 0
                        for search_variant in search_variants:
                            variant_score = 0
                            
                            # Точное совпадение имени - максимальный приоритет
                            if city_name_lower == search_variant:
                                variant_score += 100
                            # Имя начинается с искомого и длина схожая - очень высокий приоритет  
                            elif city_name_lower.startswith(search_variant) and len(city_obj.name) <= len(search_variant) + 3:
                                variant_score += 50
                            # Имя начинается с искомого - высокий приоритет
                            elif city_name_lower.startswith(search_variant):
                                variant_score += 20
                            # Содержится в имени с приоритетом по длине
                            elif search_variant in city_name_lower:
                                if len(city_obj.name) > len(search_variant) * 2:
                                    variant_score += 1
                                else:
                                    variant_score += 8
                            # В альтернативных названиях
                            elif city_obj.alternatenames and search_variant in city_obj.alternatenames.lower():
                                variant_score += 5
                            
                            max_score = max(max_score, variant_score)
                        
                        score = max_score
                        scored_cities.append((score, city_obj))
                    
                    # Сортируем и берём лучший результат
                    scored_cities.sort(key=lambda x: x[0], reverse=True)
                    city_obj = scored_cities[0][1]
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
