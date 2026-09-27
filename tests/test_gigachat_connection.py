import os
import sys
from dotenv import load_dotenv
from gigachat import GigaChat

load_dotenv()


def main():
    credentials = os.getenv("GIGACHAT_CREDENTIALS")
    model = os.getenv("GIGACHAT_MODEL", "GigaChat-2-Pro")

    if not credentials:
        print("ОШИБКА: переменная GIGACHAT_CREDENTIALS не найдена в .env")
        sys.exit(1)

    print(f"Ключ найден. Модель: {model}. Подключаемся...")

    try:
        with GigaChat(
            credentials=credentials,
            scope="GIGACHAT_API_PERS",
            model=model,
            verify_ssl_certs=False,
        ) as client:
            response = client.chat("Привет! Ответь одним предложением: ты готов помогать студентам с бюджетом?")
            print("\nОТВЕТ ОТ GIGACHAT:")
            print(response.choices[0].message.content)

    except Exception as e:
        print(f"\nОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()