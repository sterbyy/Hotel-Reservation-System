# Сценарии использования

Актор во всех сценариях — гость, который вызывает API через Swagger, PowerShell или будущий интерфейс. Клиентские сценарии описывают текущий backend. Способы запуска и поля приведены в [API-контракте](API_CONTRACT.md).

## Поиск номера

**Предусловия.** Backend доступен, миграции применены, в каталоге могут быть номера.

**Основной поток.** Гость вводит даты и число гостей. `GET /api/rooms/search` проверяет параметры, вместимость и пересечения активных броней на период `[check_in, check_out)`. Гость получает `200` со списком и открывает карточку через `GET /api/rooms/{room_id}`.

**Альтернативный поток.** Свободных подходящих номеров нет. API возвращает `200 []`, и гость может изменить даты или число гостей.

**Исключительный поток.** Некорректные даты, число гостей или ID дают `422`. Если карточка запрошена по ID отсутствующего номера, API возвращает `404`.

## Бронирование и demo-оплата

**Предусловия.** Гость выбрал номер и период. Доступность будет повторно проверена при создании.

**Основной поток.** Гость отправляет `POST /api/bookings`. Backend блокирует номер, проверяет доступность, сохраняет бронь `PENDING`, цену и хеш токена. После commit гость получает `201` с ID и одноразово выдаваемым токеном доступа. Затем он отправляет `POST /api/bookings/{booking_id}/payment` с заголовком `X-Booking-Access-Token` и результатом `SUCCEEDED`. API возвращает `200` с `CONFIRMED` и `payment.status = SUCCEEDED`.

**Альтернативный поток.** Результат `FAILED` возвращает `200`; бронь остаётся `PENDING`, платёж получает `FAILED`. Гость может повторить запрос с `SUCCEEDED`. Повтор уже сохранённого результата возвращает текущее состояние без нового вызова шлюза.

**Исключительный поток.** Для создания превышение вместимости даёт `400`, отсутствующий номер — `404`, пересечение — `409`. Отсутствующий или неверный токен в запросе оплаты даёт `404`. Оплата отменённой брони или запрос `FAILED` после подтверждения дают `409`. Некорректные входные данные дают `422`.

## Отмена

**Предусловия.** У гостя есть ID и токен. Для первой отмены текущая календарная дата UTC должна быть раньше даты заезда.

**Основной поток.** Гость отправляет `POST /api/bookings/{booking_id}/cancel`. При отмене оплаченной брони за два календарных дня или раньше backend сохраняет `CANCELLED`, платёж `REFUNDED` и полную сумму возврата. Гость получает `200`, а номер снова доступен на этот период.

**Альтернативный поток.** Неоплаченная бронь отменяется без возврата. За один календарный день до заезда оплаченная бронь отменяется без возврата, а платёж остаётся `SUCCEEDED`. Повторная отмена возвращает сохранённое состояние без повторного возврата.

**Исключительный поток.** Несуществующая или недоступная по токену бронь даёт `404`. В день заезда или позднее первая отмена даёт `409`. Некорректный ID даёт `422`.

## Диаграммы последовательностей

### Создание брони

```mermaid
sequenceDiagram
    actor Guest as Гость
    participant API as FastAPI / bookings
    participant Service as BookingService
    participant Rooms as RoomRepository
    participant Bookings as BookingRepository
    participant DB as PostgreSQL
    participant Events as BookingEventPublisher

    Guest->>API: POST /api/bookings
    API->>Service: create
    Service->>DB: Начать транзакцию READ COMMITTED
    Service->>Rooms: lock(room_id)
    Rooms->>DB: FOR UPDATE rooms
    opt Номер найден и подходит по вместимости
        Service->>Bookings: overlaps
        Bookings->>DB: Проверить PENDING и CONFIRMED на пересечение
    end
    alt Номер найден, подходит и свободен
        Service->>Bookings: add PENDING с ценой и хешем токена
        Bookings->>DB: INSERT bookings
        Service->>DB: COMMIT
        Service->>Events: publish CREATED
        Events->>Events: AuditSubscriber и DemoNotificationSubscriber
        API-->>Guest: 201, PENDING и access_token
    else Номер отсутствует, слишком мал или занят
        Service->>DB: ROLLBACK
        API-->>Guest: 404, 400 или 409
    end
```

### Demo-оплата

```mermaid
sequenceDiagram
    actor Guest as Гость
    participant API as FastAPI / bookings
    participant Service as BookingService
    participant Repo as BookingRepository
    participant DB as PostgreSQL
    participant Factory as DemoPaymentGatewayFactory
    participant Adapter as DemoPaymentAdapter
    participant Events as BookingEventPublisher

    Guest->>API: POST /api/bookings/{booking_id}/payment с токеном и outcome
    API->>Service: pay
    Service->>DB: Начать транзакцию
    Service->>Repo: lock по ID и хешу токена
    Repo->>DB: FOR UPDATE OF rooms при совпадении токена
    Repo->>DB: FOR UPDATE bookings для того же номера, если найден
    alt Бронь недоступна
        Service->>DB: ROLLBACK
        API-->>Guest: 404
    else Бронь доступна
        Service->>Repo: get_payment если бронь не отменена
        alt Запрещённый переход
            Service->>DB: ROLLBACK
            API-->>Guest: 409
        else Повтор сохранённого результата
            Service->>DB: Завершить транзакцию без изменений
            API-->>Guest: 200, текущее состояние
        else Новая попытка
            Service->>Factory: create_gateway
            Service->>Adapter: charge(outcome)
            alt Успех
                Service->>DB: CONFIRMED и SUCCEEDED
            else Отказ
                Service->>DB: Сохранить FAILED, бронь остаётся PENDING
            end
            Service->>DB: COMMIT
            Service->>Events: publish CONFIRMED или PAYMENT_FAILED
            API-->>Guest: 200, состояние брони и платежа
        end
    end
```

### Отмена

```mermaid
sequenceDiagram
    actor Guest as Гость
    participant API as FastAPI / bookings
    participant Service as BookingService
    participant Repo as BookingRepository
    participant DB as PostgreSQL
    participant Policy as CancellationPolicy
    participant Gateway as DemoPaymentGatewayFactory и DemoPaymentAdapter
    participant Events as BookingEventPublisher

    Guest->>API: POST /api/bookings/{booking_id}/cancel с токеном
    API->>Service: cancel
    Service->>DB: Начать транзакцию
    Service->>Repo: lock по ID и хешу токена
    Repo->>DB: FOR UPDATE OF rooms при совпадении токена
    Repo->>DB: FOR UPDATE bookings для того же номера, если найден
    alt Бронь недоступна
        Service->>DB: ROLLBACK
        API-->>Guest: 404
    else Бронь доступна
        Service->>Repo: get_payment
        alt Уже CANCELLED
            Service->>DB: Завершить транзакцию без изменений
            API-->>Guest: 200, сохранённое состояние
        else PENDING или CONFIRMED
            Service->>Policy: decide через UnpaidCancellationPolicy или PaidCancellationPolicy
            alt Отмена запрещена или требуемый возврат невозможен
                Service->>DB: ROLLBACK
                API-->>Guest: 409
            else Отмена разрешена
                opt Назначен полный возврат
                    Service->>Gateway: create_gateway и refund(total_price)
                    Service->>DB: Сохранить REFUNDED и refunded_amount
                end
                Service->>DB: Сохранить CANCELLED и COMMIT
                Service->>Events: publish CANCELLED
                API-->>Guest: 200, отменённая бронь
            end
        end
    end
```

В каждой диаграмме событие публикуется только после успешного commit. При ошибке записи транзакция откатывается без события.
