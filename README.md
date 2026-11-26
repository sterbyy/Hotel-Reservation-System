# Hotel Reservation System

Backend учебного прототипа на FastAPI, Pydantic, SQLAlchemy и PostgreSQL. Гость может найти свободный номер, создать бронь и использовать выданный токен для просмотра, демонстрационной оплаты и отмены.

[API-контракт](docs/API_CONTRACT.md) · [Схема PostgreSQL](docs/DB_CONTRACT.md) · [Паттерны и UML](docs/DESIGN_PATTERNS.md) · [Use Cases и последовательности](docs/USE_CASES.md) · [SAST](docs/SAST.md)

## Локальный запуск

Нужны Python 3.11+ и PostgreSQL. Команды ниже рассчитаны на PowerShell и выполняются из корня репозитория. Для работы с PostgreSQL через терминал добавьте его `bin` в `PATH`.

1. Создайте пустую базу `hotel` и отдельную роль `hotel_app` с правами владельца базы. Например, из `psql -U postgres -d postgres` выполните следующие команды. `\password` запросит пароль интерактивно.

   ```sql
   CREATE ROLE hotel_app LOGIN;
   \password hotel_app
   CREATE DATABASE hotel OWNER hotel_app;
   ```

2. Установите зависимости и скопируйте пример конфигурации.

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

3. В `.env` укажите свой `DATABASE_URL` с драйвером `postgresql+psycopg`. Специальные символы в пароле URL-кодируйте. Задайте `CORS_ORIGINS` через запятую, если React запускается на другом origin. Пример разрешает `http://localhost:5173`. Переменные процесса имеют приоритет над `.env`.

4. Примените миграции к отдельной локальной базе прототипа. Если на ней уже применена `0001_prototype`, команда установит следующую ревизию с сохранением данных.

   ```powershell
   .\.venv\Scripts\alembic.exe upgrade head
   .\.venv\Scripts\alembic.exe check
   ```

5. Заполните каталог в отдельной локальной базе. Укажите адрес и имя той же базы, к которой подключите приложение.

   ```powershell
   psql -h 127.0.0.1 -U hotel_app -d hotel -v ON_ERROR_STOP=1 -f seed.sql
   ```

   Seed добавляет `Standard Twin (Demo)` на двоих за `25000.50` KZT и `Family Room (Demo)` на четверых за `42000.00` KZT за ночь. Повторный запуск пропускает совпадающие демонстрационные названия и сохраняет существующие данные. ID номеров возвращает поиск.

6. Запустите приложение.

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
   ```

   Во втором терминале проверьте подключение.

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/health
   ```

   На Linux и macOS используйте `python3` для создания окружения, затем `.venv/bin/python` и `.venv/bin/alembic`.

Swagger UI доступен по `http://127.0.0.1:8000/docs`, OpenAPI JSON по `http://127.0.0.1:8000/openapi.json`. `GET /health` возвращает `200 {"status":"ok"}`, когда PostgreSQL отвечает на запрос, и `503 {"detail":"Database unavailable"}`, когда подключение недоступно.

## Контракт для React

Даты передаются в формате `YYYY-MM-DD`. Выезд должен быть позже заезда. Дата выезда исключена из срока брони, поэтому новый гость может заехать в тот же день. `guests` и ID — положительные целые числа. Тарифы и итоговые суммы возвращаются строками с двумя знаками после точки. Валюта прототипа — KZT.

### Поиск номеров

```http
GET /api/rooms/search?check_in=2030-06-10&check_out=2030-06-13&guests=2
```

`200 OK`

```json
[
  {
    "id": 1,
    "name": "Standard Twin (Demo)",
    "category": "standard",
    "capacity": 2,
    "nightly_rate": "25000.50"
  },
  {
    "id": 2,
    "name": "Family Room (Demo)",
    "category": "family",
    "capacity": 4,
    "nightly_rate": "42000.00"
  }
]
```

Если подходящих свободных номеров нет, ответ — `200 []`.

### Карточка номера

```http
GET /api/rooms/1
```

`200 OK`

```json
{
  "id": 1,
  "name": "Standard Twin (Demo)",
  "category": "standard",
  "capacity": 2,
  "nightly_rate": "25000.50",
  "description": "Two single beds",
  "amenities": ["Wi-Fi"]
}
```

### Создание брони

```http
POST /api/bookings
Content-Type: application/json

{"room_id":1,"check_in":"2030-06-10","check_out":"2030-06-13","guests":2}
```

`201 Created`

```json
{
  "id": 1,
  "room_id": 1,
  "status": "PENDING",
  "check_in": "2030-06-10",
  "check_out": "2030-06-13",
  "guests": 2,
  "total_price": "75001.50",
  "access_token": "<токен из ответа создания>"
}
```

Поле `id` в ответе — номер брони. Сумма равна тарифу на момент записи, умноженному на число ночей. Бронь хранит эту сумму после изменения тарифа. При `409` номер уже занят на выбранные даты, и интерфейс может обновить выдачу. Секретный `access_token` выдаётся только при создании. Для дальнейших запросов передавайте его в заголовке `X-Booking-Access-Token`.

| HTTP | Когда | Тело ответа |
| --- | --- | --- |
| `400` | Для брони указано больше гостей, чем вмещает номер | `{"detail":"Guest count exceeds room capacity"}` |
| `404` | Номер для карточки или брони отсутствует | `{"detail":"Room not found"}` |
| `409` | Бронь пересекается с существующей | `{"detail":"Room is unavailable for the selected dates"}` |
| `422` | Ошибка валидации пути, параметров или тела запроса | `{"detail":[{"loc":["query","guests"],"msg":"Input should be greater than 0","type":"greater_than"}]}` |

## Демонстрационный сценарий

После запуска seed и backend выполните сценарий во втором окне PowerShell. Он бронирует `Standard Twin (Demo)` на три ночи с заездом через три дня, читает бронь, проводит демонстрационную оплату и отменяет с полным возвратом.

```powershell
$base = 'http://127.0.0.1:8000'
$arrival = [DateTime]::UtcNow.Date.AddDays(3)
$checkIn = $arrival.ToString('yyyy-MM-dd')
$checkOut = $arrival.AddDays(3).ToString('yyyy-MM-dd')
$rooms = Invoke-RestMethod "$base/api/rooms/search?check_in=$checkIn&check_out=$checkOut&guests=2"
$room = $rooms | Where-Object { $_.name -eq 'Standard Twin (Demo)' } | Select-Object -First 1
if (-not $room) { throw 'Standard Twin (Demo) недоступен на выбранные даты' }

$body = @{room_id = $room.id; check_in = $checkIn; check_out = $checkOut; guests = 2}
$booking = Invoke-RestMethod "$base/api/bookings" -Method Post -ContentType 'application/json' -Body ($body | ConvertTo-Json)
$bookingUrl = "$base/api/bookings/$($booking.id)"
$bookingHeaders = @{'X-Booking-Access-Token' = $booking.access_token}

Invoke-RestMethod $bookingUrl -Headers $bookingHeaders
Invoke-RestMethod "$bookingUrl/payment" -Method Post -Headers $bookingHeaders -ContentType 'application/json' -Body '{"outcome":"SUCCEEDED"}'
Invoke-RestMethod "$bookingUrl/cancel" -Method Post -Headers $bookingHeaders
```

Ожидаемые статусы — `PENDING`, `CONFIRMED`, `CANCELLED`. При тарифе из seed итоговая цена и полный возврат равны `75001.50` KZT. Последний ответ содержит `payment.status = REFUNDED`. Чтобы проверить отказ, перед успешной оплатой отправьте тот же запрос с `{"outcome":"FAILED"}`. Бронь останется `PENDING`, а успешную попытку можно выполнить следом.

## Интеграция с командной схемой

В доступных ветках ещё нет общей схемы БД и frontend-контракта. Миграции `0001_prototype` и `0002_booking_lifecycle`, а также валюта KZT требуют проверки владельцем БД. Новая миграция сохраняет старые брони. Для них нет токенов, поэтому управлять ими через новые endpoints нельзя. На общей БД применяйте согласованные миграции команды. [Что проверить перед переносом](docs/DB_CONTRACT.md#решения-команды-перед-подключением)

Репозитории формируют параметризованные SQL-запросы. Пул создаётся при запуске экземпляра приложения, сессия выделяется на запрос. Создание, оплата и отмена сначала блокируют строку номера. Оплата и отмена затем блокируют строку брони и сохраняют состояние брони и платежа одной транзакцией. События демо-уведомления и аудита публикуются после commit.

## Тесты

Создайте отдельную пустую PostgreSQL-базу с суффиксом `_test`, например `CREATE DATABASE hotel_test OWNER hotel_app;`. Используйте тестовую роль или локальное окружение и укажите подключение в переменной процесса.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:TEST_DATABASE_URL = "postgresql+psycopg://hotel_app:CHANGE_ME@127.0.0.1:5432/hotel_test"
.\.venv\Scripts\python.exe -m pytest -q
```

Роль должна иметь право создать схему в тестовой БД. Тесты создают временную схему со случайным именем, накатывают миграцию и удаляют эту схему после прогона. Без `TEST_DATABASE_URL` интеграционные тесты пропускаются. Проверка конкурентности отправляет два HTTP-запроса и через PostgreSQL подтверждает, что обе транзакции ждут блокировку одной строки.

Для повторной статической проверки перед сдачей используйте [команды Bandit](docs/SAST.md).

## Ограничения прототипа

- `PENDING` и `CONFIRMED` занимают номер, `CANCELLED` освобождает его. `PENDING` автоматически не истекает.
- API работает без регистрации и восстановления токена. Платёж и возврат демонстрационные, без банковских реквизитов и внешних запросов.
- Уведомления отображаются в логах при уровне INFO. События не сохраняются для повторной доставки.
