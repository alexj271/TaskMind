from app.services.openai_tools import OpenAIService
from app.utils.prompt_manager import prompt_manager


async def generate_dialogue_summary(messages: list[str], previous_summary: str = "") -> str:
    """
    Генерирует summary диалога на основе предыдущего summary и последних сообщений.

    Args:
        messages: Список сообщений в формате "Роль: Сообщение"
        previous_summary: Предыдущее резюме диалога (может быть пустым)

    Returns:
        Новое резюме диалога
    """
    if not messages:
        return previous_summary

    # Если сообщений мало и нет предыдущего summary, возвращаем простое резюме
    if len(messages) <= 2 and not previous_summary:
        # Простая логика для коротких диалогов
        user_messages = [msg for msg in messages if msg.startswith("Пользователь:") or msg.startswith("user:")]
        if user_messages:
            last_msg = user_messages[-1]
            # Убираем префикс роли
            if last_msg.startswith("Пользователь: "):
                return last_msg.replace("Пользователь: ", "")[:200]
            elif last_msg.startswith("user: "):
                return last_msg.replace("user: ", "")[:200]
        return ""

    try:
        # Используем OpenAI для генерации summary
        openai_service = OpenAIService()

        # Формируем контекст для AI
        context_parts = []
        if previous_summary:
            context_parts.append(f"Предыдущее резюме: {previous_summary}")

        context_parts.append("Сообщения:")
        for msg in messages:
            context_parts.append(f"- {msg}")

        context = "\n".join(context_parts)

        # Загружаем промпт для summarization
        system_prompt = prompt_manager.render("dialogue_summary")

        response = await openai_service.client.chat.completions.create(
            model=openai_service.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=300,
            temperature=0.3  # Низкая температура для консистентности
        )

        new_summary = response.choices[0].message.content.strip()

        # Очищаем от лишних символов
        new_summary = new_summary.strip('"').strip("'")

        return new_summary

    except Exception as e:
        # Fallback: возвращаем последнее пользовательское сообщение
        print(f"Error generating dialogue summary: {e}")
        user_messages = [msg for msg in messages if msg.startswith("Пользователь:")]
        if user_messages:
            return user_messages[-1].replace("Пользователь: ", "")[:200]
        return previous_summary
