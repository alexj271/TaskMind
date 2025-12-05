"""
Простой тест новой функциональности detect_timezone
"""
import pytest
import asyncio
from app.utils.datetime_parser import detect_timezone, AmbiguousCityError


@pytest.mark.asyncio  
async def test_ambiguous_city_error():
    """Тест обработки неоднозначных городов"""
    from tortoise import Tortoise
    from app.core.db import TORTOISE_ORM
    
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Тест без указания страны для города Moscow - должен вызвать ошибку
        with pytest.raises(AmbiguousCityError) as exc_info:
            await detect_timezone(city="Moscow")
        
        error = exc_info.value
        assert error.city_name == "Moscow"
        assert len(error.cities_info) > 1  # Должно быть несколько городов
        assert "Найдено" in str(error)
        assert "Пожалуйста, укажите страну" in str(error)
        
        # Проверяем что в ошибке есть информация о городах
        cities_info = error.cities_info
        assert all('name' in info for info in cities_info)
        assert all('country_code' in info for info in cities_info)
        assert all('timezone' in info for info in cities_info)
        
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_city_with_country():
    """Тест определения города с указанием страны"""
    from tortoise import Tortoise
    from app.core.db import TORTOISE_ORM
    
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        # Тест с указанием страны - должен найти конкретный город
        result = await detect_timezone(city="Moscow", country="RU")
        assert result == "UTC+3"
        
        result = await detect_timezone(city="Moscow", country="US") 
        assert result is not None  # Должен найти один из американских Moscow
        assert result.startswith("UTC")
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_unknown_city_with_country():
    """Тест неизвестного города с указанием страны"""
    from tortoise import Tortoise
    from app.core.db import TORTOISE_ORM
    
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        result = await detect_timezone(city="НеизвестныйГород", country="RU")
        assert result is None
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v"])