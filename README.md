# Zadanie-6105

Тестовое задание для стажировки в Avito.tech

## Run app with docker

Для запуска приложения выполните следующие шаги:
- Соберите docker образ следующей командой:
    ```
    docker build -t my_flask_app .
    ```
- Запустите docker контейнер с помощью:
    ```
    docker run -d -p 8080:8080 my_flask_app
    ```
    При необходимости переопределите переменные окружения на валидные значения.