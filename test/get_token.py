#!/usr/bin/env python3
"""
Скрипт для получения API токена через логин.

Использование:
python test/get_token.py --username admin --password yourpassword
"""

import argparse
import requests
import json
import sys


def get_api_token(username: str, password: str, api_url: str = "http://localhost:8000/api") -> str:
    """Получить API токен через логин"""
    try:
        # Формируем данные для логина
        login_data = {
            "username": username,
            "password": password
        }

        # Отправляем запрос на логин
        response = requests.post(
            f"{api_url}/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        response.raise_for_status()

        # Извлекаем токен из JSON ответа
        token_data = response.json()
        token = token_data.get("access_token")

        if not token:
            print("❌ Ошибка: токен не найден в ответе")
            return None

        print("✅ Успешная авторизация!")
        print(f"🔑 API Token: {token}")
        print("\n💡 Используйте этот токен в integration_test.py:")
        print(f"python test/integration_test.py --client-id X --server-id Y --token {token}")

        return token

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("❌ Ошибка авторизации: неверное имя пользователя или пароль")
        else:
            print(f"❌ HTTP ошибка: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

    return None


def main():
    parser = argparse.ArgumentParser(description="Получить API токен для тестирования")
    parser.add_argument("--username", required=True, help="Имя пользователя")
    parser.add_argument("--password", required=True, help="Пароль")
    parser.add_argument("--api-url", default="http://localhost:8000/api", help="Базовый URL API")

    args = parser.parse_args()

    token = get_api_token(args.username, args.password, args.api_url)

    if token:
        # Сохраняем токен в файл для удобства
        try:
            with open("/tmp/api_token.txt", "w") as f:
                f.write(token)
            print("💾 Токен сохранен в /tmp/api_token.txt")
        except:
            pass

        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()