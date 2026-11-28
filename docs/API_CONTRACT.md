# API-контракт для React

Локальный backend доступен по `http://127.0.0.1:8000`. Интерактивная документация находится по адресу `/docs`, машинная схема — по `/openapi.json`. Примеры рассчитаны на PowerShell и `curl.exe`. Для запросов с данными загрузите локальный каталог через `seed.sql` по инструкции в [README](../README.md). В URL и теле запроса используйте ID номера из поиска и ID брони из ответа создания.

## Общие правила

- Даты — существующие календарные даты в формате `YYYY-MM-DD`. `check_out` строго позже `check_in`. Период включает заезд и исключает выезд, поэтому выезд и следующий заезд могут приходиться на один день.
- Для параметров `guests` и `room_id` допустимы целые числа от `1` до `2147483647`. В query и path передавайте их цифрами, в JSON — числами без кавычек и дробной части. Лишние параметры поиска и лишние поля JSON брони дают `422`.
- `nightly_rate` и `total_price` — десятичные строки с двумя знаками после точки в текущей PostgreSQL-схеме. KZT — предварительная валюта прототипа. Поля валюты в API нет.

## Методы

| Метод и путь | Успех | Ошибки метода |
| --- | --- | --- |
| `GET /health` | `200`, объект со статусом | `503` |
| `GET /api/rooms/search` | `200`, массив номеров | `422` |
| `GET /api/rooms/{room_id}` | `200`, карточка номера | `404`, `422` |
| `POST /api/bookings` | `201`, объект брони | `400`, `404`, `409`, `422` |
| `GET /api/bookings/{booking_id}` | `200`, состояние брони и платежа | `404`, `422` |
| `POST /api/bookings/{booking_id}/payment` | `200`, состояние брони и платежа | `404`, `409`, `422` |
| `POST /api/bookings/{booking_id}/cancel` | `200`, состояние брони и платежа | `404`, `409`, `422` |

### Проверка подключения

`GET /health` выполняет `SELECT 1` и возвращает `{"status":"ok"}` при доступной БД. `200` подтверждает подключение, а наличие таблиц проверяется отдельно миграциями и запросами к API. При недоступной БД возвращается `503 {"detail":"Database unavailable"}`.

### Поиск номеров

Все три query-параметра обязательны.

| Параметр | Тип | Значение |
| --- | --- | --- |
| `check_in` | `string`, формат `date` | Дата заезда |
| `check_out` | `string`, формат `date` | Дата выезда |
| `guests` | `integer` | Минимальная требуемая вместимость |

```powershell
curl.exe -i 'http://127.0.0.1:8000/api/rooms/search?check_in=2030-06-10&check_out=2030-06-13&guests=2'
```

Ответ `200` содержит массив `RoomSummary`, отсортированный по возрастанию `id`. У всех элементов обязательны поля `id` и `capacity` типа `integer`, а также `name`, `category` и `nightly_rate` типа `string`.

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

Если в базе есть только номера из seed, тот же поиск с `guests=5` вернёт `200` с телом `[]`. Пустой массив также возвращается, если подходящие по вместимости номера уже заняты на выбранный период.

### Карточка номера

```powershell
curl.exe -i 'http://127.0.0.1:8000/api/rooms/1'
```

Путь принимает обязательный целочисленный `room_id`. Ответ `200` содержит поля `RoomSummary` и два дополнительных обязательных поля, `description` типа `string` и `amenities` типа `array<string>`. Карточку можно открыть независимо от доступности номера на конкретные даты.

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

Отправляйте `Content-Type: application/json`. Все четыре поля тела обязательны. `room_id` и `guests` имеют тип `integer`, `check_in` и `check_out` — тип `string` с форматом `date`.

```powershell
'{"room_id":1,"check_in":"2030-06-10","check_out":"2030-06-13","guests":2}' |
  curl.exe -i -X POST 'http://127.0.0.1:8000/api/bookings' -H 'Content-Type: application/json' --data-binary '@-'
```

Ответ `201` сохраняет прежние поля и добавляет обязательную строку `access_token`. Он содержит все поля запроса, целочисленный номер брони `id`, строковый `status` со значением `PENDING` и строковый `total_price`. Сумма равна тарифу на момент записи, умноженному на число ночей.

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

Поиск показывает доступность на момент запроса. Повторная отправка примера после успешного создания брони пересечётся с сохранённой бронью и вернёт `409`. При таком ответе интерфейс может обновить выдачу и предложить другие варианты проживания.

```json
{"detail":"Room is unavailable for the selected dates"}
```

### Доступ к брони

Сохраните `access_token` из ответа создания. Токен выдаётся только в этом ответе. Для чтения состояния, оплаты и отмены передавайте его в заголовке `X-Booking-Access-Token`. В Swagger выберите **Authorize** и укажите значение для `BookingAccessToken`. Для сетевого окружения передавайте токен только через HTTPS и исключайте его из URL, логов и аналитики. Успешные ответы бронирования содержат `Cache-Control: no-store`.

Обязательный `booking_id` в пути — целое число от `1` до `2147483647`. При отсутствующем или неверном токене, неизвестном ID или обращении к записи, созданной до введения токенов, API возвращает один ответ `404 {"detail":"Booking not found"}`. Восстановление токена не предусмотрено.

```powershell
$bookingId = 1
$token = '<значение access_token из ответа 201>'
$bookingUrl = "http://127.0.0.1:8000/api/bookings/$bookingId"
$accessHeader = "X-Booking-Access-Token: $token"
curl.exe -i $bookingUrl -H $accessHeader
```

Три защищённых метода используют один ответ `BookingStateResponse`. Он содержит `id`, `room_id`, `guests` как целые числа, `check_in` и `check_out` как даты, `total_price` как десятичную строку, `status` как `PENDING`, `CONFIRMED` или `CANCELLED` и обязательное поле `payment`. До первой попытки `payment` равно `null`. После попытки это объект со статусом `FAILED`, `SUCCEEDED` или `REFUNDED` и полем `refunded_amount`. Оно содержит десятичную строку при возврате и `null` в остальных случаях. Поля `access_token` и хеша в ответе нет.

### Demo-оплата

`POST /api/bookings/{booking_id}/payment` принимает только обязательное поле `outcome` со значением `SUCCEEDED` или `FAILED`. Другие поля дают `422`. Успешный результат переводит `PENDING` в `CONFIRMED`. Отказ демо-шлюза возвращает `200` с `payment.status = FAILED` и оставляет бронь в `PENDING`. После отказа можно повторить оплату с `SUCCEEDED`.

```powershell
'{"outcome":"SUCCEEDED"}' |
  curl.exe -i -X POST "$bookingUrl/payment" -H $accessHeader -H 'Content-Type: application/json' --data-binary '@-'
```

```json
{
  "id": 1,
  "room_id": 1,
  "status": "CONFIRMED",
  "check_in": "2030-06-10",
  "check_out": "2030-06-13",
  "guests": 2,
  "total_price": "75001.50",
  "payment": {"status": "SUCCEEDED", "refunded_amount": null}
}
```

Повтор того же результата после отказа или подтверждения возвращает сохранённое состояние без нового вызова шлюза. Запрос `FAILED` после подтверждения и оплата после отмены дают `409`. Демо-шлюз не принимает банковские реквизиты и не обращается во внешнюю сеть.

### Отмена и возврат

`POST /api/bookings/{booking_id}/cancel` вызывается без тела. Правила используют разницу календарных дат между заездом и текущей датой UTC.

| Статус брони | До заезда осталось | Результат |
| --- | --- | --- |
| `PENDING` | Один календарный день или больше | `CANCELLED`, возврата нет. При наличии неуспешной попытки платёж остаётся `FAILED` |
| `CONFIRMED` | Два календарных дня или больше | `CANCELLED`, платёж `REFUNDED`, возвращена вся сохранённая сумма |
| `CONFIRMED` | Один календарный день | `CANCELLED`, платёж остаётся `SUCCEEDED`, сумма возврата равна `null` |
| `PENDING` или `CONFIRMED` | День заезда или позднее | `409`, состояние сохраняется |
| `CANCELLED` | Любой день | `200`, текущее состояние без повторного возврата |

```powershell
curl.exe -i -X POST "$bookingUrl/cancel" -H $accessHeader
```

Например, после отмены оплаченной брони за два календарных дня её статус будет `CANCELLED`, а поле платежа — `{"status":"REFUNDED","refunded_amount":"75001.50"}`. Отменённая бронь освобождает номер. В гонке оплаты с отменой каждая операция возвращает состояние, записанное её транзакцией. Для получения актуального состояния используйте защищённый `GET`.

## Ошибки

| HTTP | Условие | Тело JSON |
| --- | --- | --- |
| `400` | При бронировании превышена вместимость номера | `{"detail":"Guest count exceeds room capacity"}` |
| `404` | Указанный номер отсутствует | `{"detail":"Room not found"}` |
| `404` | Бронь недоступна по ID и токену | `{"detail":"Booking not found"}` |
| `409` | Запрошенные даты пересекаются с бронью этого номера | `{"detail":"Room is unavailable for the selected dates"}` |
| `409` | Оплата отменённой брони | `{"detail":"Cancelled booking cannot be paid"}` |
| `409` | Запрос результата `FAILED` после подтверждения | `{"detail":"Confirmed booking cannot be paid again"}` |
| `409` | Отмена в день заезда или позднее | `{"detail":"Booking cannot be cancelled on or after check-in"}` |
| `409` | Сохранённое состояние платежа несовместимо с запрошенной операцией | `{"detail":"Booking has an inconsistent payment state"}` |
| `422` | Не прошла проверка параметров пути, параметров поиска или тела | `{"detail":[{"loc":["query","guests"],"msg":"Input should be greater than 0","type":"greater_than"}]}` |
| `503` | Запрос `/health` не смог обратиться к БД | `{"detail":"Database unavailable"}` |

У `422` каждый элемент `detail` содержит `loc` (массив строк и целых чисел), `msg` и `type` (строки). `loc` может указывать на всю группу параметров или всё тело, например при неверном порядке дат. Текст `msg` зависит от валидатора. Для непредвиденных серверных ошибок JSON-формат не гарантирован.

## Запуск и CORS

Перед запуском подготовьте локальную БД, `.env` и зависимости по [README](../README.md#локальный-запуск). Затем запустите backend из корня репозитория.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

`CORS_ORIGINS` — список точных origins через запятую. Origin включает схему, хост и порт, без пути и завершающего слеша. В [.env.example](../.env.example) по умолчанию указан `http://localhost:5173`. Для React по обоим локальным адресам Vite можно указать два origin.

```dotenv
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Если список пуст, middleware CORS не включается. Для разрешённых origins поддерживаются запросы `GET` и `POST`, preflight `OPTIONS` и заголовки `Content-Type` и `X-Booking-Access-Token`. Передача браузерных credentials через CORS не настроена. Для общего окружения укажите фактический origin React. Запросы через Swagger на самом backend идут с того же origin.

Запускайте тесты из корня репозитория. Замените строку подключения на свою тестовую БД PostgreSQL с именем на `_test`. Роль должна иметь право создать схему.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:TEST_DATABASE_URL = 'postgresql+psycopg://hotel_test:CHANGE_ME@127.0.0.1:5432/hotel_test'
.\.venv\Scripts\python.exe -m pytest -q
```

В проверенном окружении Starlette 1.10.0 выдаёт предупреждение при импорте `TestClient` через FastAPI. Старый `httpx` используется как резервный клиент, когда `httpx2` отсутствует. Для перехода сначала проверьте `httpx2` в отдельном тестовом окружении с той же версией FastAPI и Starlette, затем повторите все тесты и уточните диапазон поддерживаемых версий перед заменой зависимости в `requirements-dev.txt`. [Документация Starlette TestClient](https://starlette.dev/testclient/)
