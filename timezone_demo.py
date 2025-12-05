"""
Демонстрация новой функциональности detect_timezone с обработкой неоднозначных городов
"""
import asyncio
from tortoise import Tortoise
from app.core.db import TORTOISE_ORM
from app.utils.datetime_parser import detect_timezone, AmbiguousCityError


async def demo_timezone_detection():
    """Демонстрация определения timezone с обработкой неоднозначности"""
    await Tortoise.init(config=TORTOISE_ORM)
    
    try:
        print("🌍 Демонстрация определения часовых поясов")
        print("=" * 50)
        
        # 1. Успешное определение с указанием страны
        print("\n✅ Успешные случаи с указанием страны:")
        
        result = await detect_timezone(city="Moscow", country="RU")
        print(f"   Moscow, RU: {result}")
        
        # 2. Попытка без указания страны для неоднозначного города
        print("\n⚠️ Случай с неоднозначным городом (без страны):")
        
        try:
            result = await detect_timezone(city="Moscow")
            print(f"   Moscow: {result}")
        except AmbiguousCityError as e:
            print(f"   Ошибка: {e}")
            print(f"   Найдено городов: {len(e.cities_info)}")
            print("   Варианты:")
            for info in e.cities_info[:3]:  # Показываем первые 3
                print(f"     - {info['name']}, {info['country_code']} ({info['timezone']})")
            if len(e.cities_info) > 3:
                print(f"     ... и ещё {len(e.cities_info) - 3} городов")
        
        # 3. Точное определение с указанием страны
        print("\n✅ Точное определение после указания страны:")
        
        result = await detect_timezone(city="Moscow", country="RU")
        print(f"   Moscow, RU: {result}")
        
        result = await detect_timezone(city="Moscow", country="US")  
        print(f"   Moscow, US: {result}")
        
        # 4. Тест с другими методами определения
        print("\n🔧 Другие способы определения:")
        
        result = await detect_timezone(timezone_str="Europe/Moscow")
        print(f"   По timezone строке Europe/Moscow: {result}")
        
        result = await detect_timezone(current_time="15:30")
        print(f"   По текущему времени 15:30: {result}")
        
        print("\n🎯 Демонстрация завершена!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(demo_timezone_detection())