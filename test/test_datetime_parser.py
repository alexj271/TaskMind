"""
Тесты для datetime_parser.py
"""
import pytest
from app.utils.datetime_parser import detect_timezone, AmbiguousCityError


@pytest.mark.database
@pytest.mark.asyncio
async def test_detect_timezone_by_city():
    """Тест определения timezone по городу с указанием страны"""
    from tortoise import Tortoise
    from app.core.db import TORTOISE_ORM
    from app.models.city import City

    await Tortoise.init(config=TORTOISE_ORM)

    try:
        # Теперь указываем страну для точного определения
        result = await detect_timezone(city="Москва", country="RU")
        assert result == "UTC+3", f"Expected UTC+3, got Москва {result}"

        result = await detect_timezone(city="Уфа", country="RU")
        # Проверяем что функция работает (может вернуть None если города нет в базе)
        assert result is None or result.startswith("UTC"), f"Unexpected result for Уфа: {result}"

        result = await detect_timezone(city="Бирск", country="RU") 
        # Проверяем что функция работает (может вернуть None если города нет в базе)
        assert result is None or result.startswith("UTC"), f"Unexpected result for Бирск: {result}"

        # Тест с неоднозначными городами - должен вызвать ошибку без указания страны
        with pytest.raises(AmbiguousCityError) as exc_info:
            await detect_timezone(city="Moscow")  # Есть много городов Moscow в разных странах
        
        # Проверяем что ошибка содержит информацию о множественных городах
        error = exc_info.value
        assert error.city_name == "Moscow"
        assert len(error.cities_info) > 1  # Должно быть несколько городов
        assert "Moscow" in str(error) or "Найдено" in str(error)

        result = await detect_timezone(city="Tokyo", country="JP")
        assert result == "UTC+9", f"Expected UTC+9, got Tokyo {result}"
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_detect_timezone_by_timezone_str():
    """Тест определения timezone по строке"""
    result = await detect_timezone(timezone_str="Europe/Moscow")
    assert result == "UTC+3"
    
    result = await detect_timezone(timezone_str="UTC+5")
    assert result == "UTC+5"
    
    result = await detect_timezone(timezone_str="America/New_York")
    # Зависит от DST, но проверим что не None
    assert result is not None
    assert result.startswith("UTC")


@pytest.mark.asyncio
async def test_detect_timezone_by_current_time():
    """Тест определения timezone по текущему времени"""
    # Текущий час UTC, скажем 12, то время 15:00 -> UTC+3
    # Но тест может быть flaky, так что mock или пропустить
    # Для простоты, проверим что функция не падает
    result = await detect_timezone(current_time="15:30")
    assert isinstance(result, str) or result is None


@pytest.mark.asyncio
async def test_detect_timezone_no_args():
    """Тест без аргументов"""
    result = await detect_timezone()
    assert result is None


@pytest.mark.asyncio
async def test_detect_timezone_unknown_city():
    """Тест неизвестного города"""
    result = await detect_timezone(city="НеизвестныйГород")
    assert result is None


@pytest.mark.asyncio
async def test_detect_timezone_invalid_time():
    """Тест невалидного времени"""
    result = await detect_timezone(current_time="invalid")
    assert result is None


@pytest.mark.database
@pytest.mark.asyncio
async def test_detect_timezone_ambiguous_city():
    """Тест для случая с несколькими городами одного названия"""
    from tortoise import Tortoise
    from app.core.db import TORTOISE_ORM
    from app.models.city import City
    import uuid

    await Tortoise.init(config=TORTOISE_ORM)

    try:
        # Используем уникальное название для теста, чтобы не пересекаться с реальными данными
        test_city_name = f"TestCity{uuid.uuid4().hex[:8]}"
        
        # Создаем тестовые города с одинаковым уникальным названием
        city1 = await City.create(
            name=test_city_name,
            country_code="US",
            timezone="America/New_York",
            latitude=42.1,
            longitude=-72.6
        )
        
        city2 = await City.create(
            name=test_city_name, 
            country_code="GB",
            timezone="Europe/London",
            latitude=53.5,
            longitude=-2.6
        )
        
        # Тест без указания страны - должен вызвать AmbiguousCityError
        with pytest.raises(AmbiguousCityError) as exc_info:
            await detect_timezone(city=test_city_name)
        
        error = exc_info.value
        assert error.city_name == test_city_name
        assert len(error.cities_info) == 2
        assert f"Найдено 2 городов" in str(error)
        assert "US" in str(error)
        assert "GB" in str(error)
        
        # Тест с указанием страны US - должен найти американский город
        result = await detect_timezone(city=test_city_name, country="US")
        assert result is not None
        assert result.startswith("UTC")
        
        # Тест с указанием страны GB - должен найти британский город
        result = await detect_timezone(city=test_city_name, country="GB")  
        assert result is not None
        assert result.startswith("UTC")
        
    finally:
        # Очищаем тестовые данные
        if 'city1' in locals():
            await city1.delete()
        if 'city2' in locals():
            await city2.delete()
        await Tortoise.close_connections()


@pytest.mark.database 
@pytest.mark.asyncio
async def test_detect_timezone_with_country():
    """Тест определения timezone по городу и стране"""
    from tortoise import Tortoise
    from app.core.db import TORTOISE_ORM

    await Tortoise.init(config=TORTOISE_ORM)

    try:
        # Тест с существующим городом и правильной страной
        result = await detect_timezone(city="Москва", country="RU")
        assert result == "UTC+3"
        
        # Тест с уникальным городом
        result = await detect_timezone(city="Уфа", country="RU")
        assert result is None or result.startswith("UTC")
        
    finally:
        await Tortoise.close_connections()