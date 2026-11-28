import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { BookingCreated } from "../api/types";
import { Gallery } from "../components/Gallery";
import { Empty, ErrorState, InlineError, Loading } from "../components/States";
import {
  addDaysIso,
  categoryLabel,
  formatMoney,
  guestsGenitive,
  guestsLabel,
  multiplyRate,
  nightsBetween,
  nightsLabel,
  todayIso,
} from "../lib/format";
import { roomGallery } from "../lib/images";
import { MAX_GUESTS, hasErrors, stayFromParams, validateStay } from "../lib/stay";
import { saveBooking } from "../lib/storage";
import { useAsync } from "../lib/useAsync";

export function RoomPage() {
  const { roomId } = useParams();
  const [params] = useSearchParams();
  const id = Number(roomId);

  const [draft, setDraft] = useState(() => stayFromParams(params));
  const [touched, setTouched] = useState(false);
  const [booking, setBooking] = useState<BookingCreated | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<unknown>(null);

  const room = useAsync((signal) => api.roomDetails(id, signal), [id]);

  const stayErrors = validateStay(draft);
  const nights = nightsBetween(draft.check_in, draft.check_out);
  const guests = Number(draft.guests);
  const capacityError =
    room.data && Number.isInteger(guests) && guests > room.data.capacity
      ? `В этом номере размещается не больше ${guestsGenitive(room.data.capacity)}.`
      : undefined;

  // Re-checks this exact room against the catalogue whenever the dates change,
  // so an occupied period is visible before the guest presses the button.
  const availability = useAsync(
    async (signal) => {
      if (hasErrors(stayErrors)) {
        return null;
      }
      const rooms = await api.searchRooms(
        { check_in: draft.check_in, check_out: draft.check_out, guests: 1 },
        signal,
      );
      return rooms.some((item) => item.id === id);
    },
    [id, draft.check_in, draft.check_out, hasErrors(stayErrors)],
  );

  const occupied = availability.data === false;
  const blocked =
    hasErrors(stayErrors) || capacityError !== undefined || occupied || booking !== null;

  async function submit() {
    setTouched(true);
    if (hasErrors(stayErrors) || capacityError || !room.data) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createBooking({
        room_id: room.data.id,
        check_in: draft.check_in,
        check_out: draft.check_out,
        guests,
      });
      setBooking(created);
      saveBooking({
        id: created.id,
        token: created.access_token,
        roomId: created.room_id,
        roomName: room.data.name,
        checkIn: created.check_in,
        checkOut: created.check_out,
        guests: created.guests,
        totalPrice: created.total_price,
        savedAt: new Date().toISOString(),
      });
    } catch (error) {
      setSubmitError(error);
      if (error instanceof ApiError && error.status === 409) {
        // The period was taken between the check and the request: refresh availability.
        availability.reload();
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!Number.isInteger(id) || id < 1) {
    return (
      <Empty title="Неверный адрес номера" description="Откройте номер из списка результатов.">
        <Link className="out" to="/rooms">
          К результатам
        </Link>
      </Empty>
    );
  }

  if (room.loading) {
    return <Loading label="Загружаем карточку номера…" />;
  }

  if (room.error) {
    if (room.error instanceof ApiError && room.error.status === 404) {
      return (
        <Empty
          title="Номер не найден"
          description="Возможно, номер убрали из каталога. Выберите другой в результатах поиска."
        >
          <Link className="out" to="/rooms">
            К результатам
          </Link>
        </Empty>
      );
    }
    return <ErrorState error={room.error} onRetry={room.reload} />;
  }

  if (!room.data) {
    return <ErrorState error={new Error("Пустой ответ сервера.")} onRetry={room.reload} />;
  }

  const current = room.data;
  const total = nights > 0 ? multiplyRate(current.nightly_rate, nights) : null;

  return (
    <>
      <div className="mut" style={{ marginBottom: 12 }}>
        <Link to={`/rooms?${params.toString()}`}>← Результаты</Link>
      </div>

      <div className="room">
        <div className="main">
          <Gallery photos={roomGallery(current.id)} roomName={current.name} />
          <h1 style={{ fontSize: 40, margin: "12px 0 0" }}>{current.name}</h1>
          <div className="mut">
            Категория «{categoryLabel(current.category)}» · до {guestsGenitive(current.capacity)}
          </div>
          <p style={{ fontSize: 16, lineHeight: 1.6, margin: "4px 0" }}>{current.description}</p>
          {current.amenities.length > 0 ? (
            <div className="chips">
              {current.amenities.map((amenity) => (
                <span key={amenity}>{amenity}</span>
              ))}
            </div>
          ) : (
            <p className="mut">Удобства для этого номера ещё не заполнены.</p>
          )}
        </div>

        <aside className="bk">
          <div className="price">
            {formatMoney(current.nightly_rate)} <small>/ ночь</small>
          </div>

          <label className="f">
            Заезд
            <input
              type="date"
              value={draft.check_in}
              min={todayIso()}
              disabled={booking !== null}
              aria-invalid={touched && stayErrors.check_in ? true : undefined}
              onChange={(event) => {
                const check_in = event.target.value;
                setDraft((value) => ({
                  ...value,
                  check_in,
                  check_out: value.check_out <= check_in ? addDaysIso(check_in, 1) : value.check_out,
                }));
              }}
            />
            {touched && stayErrors.check_in ? (
              <span className="field-error">{stayErrors.check_in}</span>
            ) : null}
          </label>

          <label className="f">
            Выезд
            <input
              type="date"
              value={draft.check_out}
              min={addDaysIso(draft.check_in || todayIso(), 1)}
              disabled={booking !== null}
              aria-invalid={touched && stayErrors.check_out ? true : undefined}
              onChange={(event) =>
                setDraft((value) => ({ ...value, check_out: event.target.value }))
              }
            />
            {touched && stayErrors.check_out ? (
              <span className="field-error">{stayErrors.check_out}</span>
            ) : null}
          </label>

          <label className="f">
            Гостей
            <input
              type="number"
              inputMode="numeric"
              min={1}
              max={Math.min(current.capacity, MAX_GUESTS)}
              step={1}
              value={draft.guests}
              disabled={booking !== null}
              aria-invalid={
                touched && (stayErrors.guests || capacityError) ? true : undefined
              }
              onChange={(event) => setDraft((value) => ({ ...value, guests: event.target.value }))}
            />
            {touched && stayErrors.guests ? (
              <span className="field-error">{stayErrors.guests}</span>
            ) : null}
            {capacityError ? <span className="field-error">{capacityError}</span> : null}
          </label>

          <div className="sum total">
            <span>
              {nights > 0
                ? `${formatMoney(current.nightly_rate)} × ${nightsLabel(nights)}`
                : "Проверьте даты"}
            </span>
            <b>{total ? formatMoney(total) : "—"}</b>
          </div>

          {!booking && availability.loading ? (
            <div className="mut" aria-live="polite">
              Проверяем доступность…
            </div>
          ) : null}

          {!booking && occupied ? (
            <div className="warn" role="status">
              Номер занят на выбранные даты. Измените период или вернитесь к результатам поиска.
            </div>
          ) : null}

          {!booking && availability.error ? (
            <div className="warn" role="status">
              Не удалось проверить доступность. Её повторно проверит сервер при бронировании.
            </div>
          ) : null}

          {submitError ? <InlineError error={submitError} /> : null}

          {booking ? (
            <div className="ok" role="status">
              <b>Бронь №{booking.id} создана</b>
              <span>
                {nightsLabel(nightsBetween(booking.check_in, booking.check_out))} ·{" "}
                {guestsLabel(booking.guests)} · {formatMoney(booking.total_price)}
              </span>
              <span>
                Код доступа выдаётся один раз. Он сохранён в этом браузере — сохраните копию, если
                будете открывать бронь в другом:
              </span>
              <code className="token">{booking.access_token}</code>
              <Link className="btn" to={`/bookings#booking-${booking.id}`}>
                Перейти к оплате
              </Link>
            </div>
          ) : (
            <button className="btn" type="button" onClick={submit} disabled={blocked || submitting}>
              {submitting ? "Создаём бронь…" : "Забронировать"}
            </button>
          )}

          <div className="note">
            Оплата демонстрационная: банковские реквизиты не запрашиваются и деньги не списываются.
          </div>
        </aside>
      </div>
    </>
  );
}
