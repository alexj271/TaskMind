#!/usr/bin/env python3
"""
Утилита для анализа отчетов по интеграционным тестам AI
"""
import json
import sys
from pathlib import Path
from datetime import datetime


def analyze_report(report_file: str):
    """Анализирует JSON отчет по тестам"""
    
    if not Path(report_file).exists():
        print(f"❌ Файл отчета не найден: {report_file}")
        return
    
    with open(report_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    print("="*80)
    print("📊 АНАЛИЗ ОТЧЕТА ПО ИНТЕГРАЦИОННЫМ ТЕСТАМ AI")
    print("="*80)
    
    # Общая информация
    print(f"🕐 Время создания: {report['timestamp']}")
    print(f"🤖 Модель AI: {report['openai_model']}")
    print(f"📈 Всего тестов: {report['summary']['total_tests']}")
    print(f"✅ Успешных: {report['summary']['successful_tests']}")
    print(f"❌ Провальных: {report['summary']['failed_tests']}")
    
    if report['summary']['failed_tests'] > 0:
        success_rate = (report['summary']['successful_tests'] / report['summary']['total_tests']) * 100
        print(f"📊 Успешность: {success_rate:.1f}%")
    
    print("\n" + "="*80)
    
    # Анализ по типам тестов
    failed_tests = [t for t in report['tests'] if not t['success']]
    successful_tests = [t for t in report['tests'] if t['success']]
    
    if failed_tests:
        print("❌ ДЕТАЛЬНЫЙ АНАЛИЗ ПРОВАЛЬНЫХ ТЕСТОВ:")
        print("="*80)
        
        for i, test in enumerate(failed_tests, 1):
            print(f"\n{i}. Тест: {test['test_name']}")
            print(f"   Входное сообщение: \"{test['input_message']}\"")
            print(f"   Ожидаемое поведение: {test['expected_behavior']}")
            print(f"   Фактическое поведение: {test['actual_behavior']}")
            
            if test.get('ai_response'):
                print(f"   AI ответ: \"{test['ai_response'][:150]}{'...' if len(test['ai_response']) > 150 else ''}\"")
            
            if test.get('function_call'):
                func_name = test['function_call'].get('function_name', 'N/A')
                print(f"   Вызванная функция: {func_name}")
                if test['function_call'].get('arguments'):
                    args = test['function_call']['arguments']
                    print(f"   Аргументы функции: {json.dumps(args, ensure_ascii=False, indent=6)}")
            else:
                print(f"   Вызванная функция: Нет")
            
            if test.get('error'):
                print(f"   Техническая ошибка: {test['error']}")
            
            print("-" * 60)
    
    if successful_tests:
        print(f"\n✅ УСПЕШНЫЕ ТЕСТЫ ({len(successful_tests)}):")
        print("="*80)
        
        for i, test in enumerate(successful_tests, 1):
            print(f"{i:2d}. {test['test_name']}: \"{test['input_message'][:50]}{'...' if len(test['input_message']) > 50 else ''}\"")
            if test.get('function_call'):
                func_name = test['function_call'].get('function_name', 'N/A')
                print(f"     -> Функция: {func_name}")
            else:
                print(f"     -> Обычный чат")
    
    # Паттерны ошибок
    if failed_tests:
        print(f"\n🔍 АНАЛИЗ ПАТТЕРНОВ ОШИБОК:")
        print("="*80)
        
        # Группируем по типу ошибки
        error_patterns = {}
        for test in failed_tests:
            actual = test['actual_behavior']
            if actual not in error_patterns:
                error_patterns[actual] = []
            error_patterns[actual].append(test)
        
        for pattern, tests in error_patterns.items():
            print(f"\n📋 Паттерн: {pattern}")
            print(f"   Количество случаев: {len(tests)}")
            print(f"   Примеры сообщений:")
            for test in tests[:3]:  # Показываем первые 3 примера
                print(f"   - \"{test['input_message']}\"")
                if test.get('ai_response'):
                    print(f"     AI ответил: \"{test['ai_response'][:100]}{'...' if len(test['ai_response']) > 100 else ''}\"")
    
    print("\n" + "="*80)
    print("📝 РЕКОМЕНДАЦИИ:")
    
    if failed_tests:
        print("• Проанализируйте паттерны ошибок для улучшения промптов")
        print("• Рассмотрите дополнительные примеры в обучающих данных")
        print("• Проверьте настройки temperature и другие параметры модели")
    else:
        print("• Все тесты прошли успешно! 🎉")
    
    print("="*80)


def find_latest_report():
    """Находит последний отчет в папке test_reports"""
    report_dir = Path(__file__).parent / "test_reports"
    
    if not report_dir.exists():
        print("❌ Папка с отчетами не найдена")
        return None
    
    reports = list(report_dir.glob("ai_integration_report_*.json"))
    
    if not reports:
        print("❌ Отчеты не найдены")
        return None
    
    # Сортируем по времени создания
    latest = max(reports, key=lambda p: p.stat().st_mtime)
    return str(latest)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        report_file = sys.argv[1]
    else:
        report_file = find_latest_report()
        if not report_file:
            sys.exit(1)
        print(f"📁 Анализируем последний отчет: {report_file}")
    
    analyze_report(report_file)