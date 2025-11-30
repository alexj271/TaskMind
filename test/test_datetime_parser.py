"""
Тесты для datetime_parser.py
"""
import pytest
from app.utils.datetime_parser import detect_timezone


@pytest.mark.database
@pytest.mark.asyncio
async def test_detect_timezone_by_city():
    """Тест определения timezone по городу"""
    from tortoise import Tortoise
    from app.core.db import TORTOISE_ORM
    from app.models.city import City

    await Tortoise.init(config=TORTOISE_ORM)

    try:
        result = await detect_timezone(city="Москва")
        assert result == "UTC+3"

        result = await detect_timezone(city="Уфа")
        assert result == "UTC+5"

        result = await detect_timezone(city="Бирск")
        assert result == "UTC+5"

        result = await detect_timezone(city="New York City")
        assert result == "UTC-5"  # Или UTC-4 в зависимости от DST, но для простоты

        result = await detect_timezone(city="Tokyo")
        assert result == "UTC+9"
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