import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { BookingState, DemoPaymentOutcome } from "../api/types";
import { StatusPill, paymentStatusLabel } from "../components/BookingStatus";
import { Empty, InlineError, Loading, describeError } from "../components/States";
import { formatFullDate, formatMoney, guestsLabel, nightsBetween, nightsLabel } from "../lib/format";
import { roomCover } from "../lib/images";
import { forgetBooking, loadBookings } from "../lib/storage";
import type { SavedBooking } from "../lib/storage";

type Loaded =
  | { kind: "loading" }
  | { kind: "ready"; state: BookingState }
  | { kind: "missing" }
  | { kind: "error"; error: unknown };

export function BookingsPage() {
  const [saved, setSaved] = useState<SavedBooking[]>(() => loadBookings());
  const [states, setStates] = useState<Record<number, Loaded>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [actionError, setActionError] = useState<Record<number, unknown>>({});

  const refresh = useCallback(async (item: SavedBooking, signal?: AbortSignal) => {
    setStates((current) => ({ ...current, [item.id]: { kind: "loading" } }));
    try {
      const state = await api.getBooking(item.id, item.token, signal);
      setStates((current) => ({ ...current, [item.id]: { kind: "ready", state } }));
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      // 404 also covers a token the server no longer accepts.
      const kind = error instanceof ApiError && error.status === 404 ? "missing" : "error";
      setStates((current) => ({
        ...current,
        [item.id]: kind === "missing" ? { kind: "missing" } : { kind: "error", error },
      }));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    for (const item of saved) {
      void refresh(item, controller.signal);
    }
    return () => controller.abort();
  }, [saved, refresh]);

  // Lets the confirmation link from the room page scroll to the fresh booking.
  useEffect(() => {
    const target = window.location.hash.slice(1);
    if (target) {
      document.getElementById(target)?.scrollIntoView({ block: "center" });
    }
  }, [saved]);

  async function act(
    item: SavedBooking,
    action: (token: string) => Promise<BookingState>,
  ): Promise<void> {
    setBusy(item.id);
    setActionError((current) => ({ ...current, [item.id]: null }));
    try {
      const state = await action(item.token);
      setStates((current) => ({ ...current, [item.id]: { kind: "ready", state } }));
    } catch (error) {
      setActionError((current) => ({ ...current, [item.id]: error }));
      void refresh(item);
    } finally {
      setBusy(null);
    }
  }

  function pay(item: SavedBooking, outcome: DemoPaymentOutcome) {
    return act(item, (token) => api.payBooking(item.id, token, outcome));
  }

  async function cancel(item: SavedBooking) {
    setConfirming(null);
    await act(item, (token) => api.cancelBooking(item.id, token));
  }

  function forget(id: number) {
    setSaved(forgetBooking(id));
  }

  if (saved.length === 0) {
    return (
      <>
        <h1>Мои брони</h1>
        <p className="lead">
          Брони, созданные в этом браузере, появляются здесь вместе с кодом доступа. Прототип не
          использует регистрацию, поэтому список хранится локально.
        </p>
        <Empty
          title="Броней пока нет"
          description="Найдите свободный номер и оформите бронь — она появится в этом списке."
        >
          <Link className="btn" to="/">
            Найти номер
          </Link>
        </Empty>
      </>
    );
  }

  return (
    <>
      <h1>Мои брони</h1>
      <p className="lead">
        Состояние каждой брони запрашивается у сервера по коду доступа из этого браузера.
      </p>

      <div className="list" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {saved.map((item) => {
          const loaded = states[item.id] ?? { kind: "loading" as const };
          const cover = roomCover(item.roomId);
          const state = loaded.kind === "ready" ? loaded.state : null;
          const nights = nightsBetween(item.checkIn, item.checkOut);
          const working = busy === item.id;
          const payment = state?.payment ?? null;

          return (
            <article className="card row" key={item.id} id={`booking-${item.id}`}>
              <div className="ph">
                <img src={cover.src} alt="" loading="lazy" />
                <span>Бронь №{item.id}</span>
              </div>
              <div className="cb">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                    alignItems: "center",
                  }}
                >
                  <h3>{item.roomName}</h3>
                  {state ? <StatusPill status={state.status} /> : null}
                </div>

                <dl className="kv">
                  <dt>Заезд</dt>
                  <dd>{formatFullDate(item.checkIn)}</dd>
                  <dt>Выезд</dt>
                  <dd>{formatFullDate(item.checkOut)}</dd>
                  <dt>Срок</dt>
                  <dd>
                    {nightsLabel(nights)} · {guestsLabel(item.guests)}
                  </dd>
                  <dt>Сумма</dt>
                  <dd>{formatMoney(state?.total_price ?? item.totalPrice)}</dd>
                  {payment ? (
                    <>
                      <dt>Платёж</dt>
                      <dd>
                        {paymentStatusLabel(payment.status)}
                        {payment.refunded_amount
                          ? ` · возврат ${formatMoney(payment.refunded_amount)}`
                          : ""}
                      </dd>
                    </>
                  ) : null}
                </dl>

                {loaded.kind === "loading" ? (
                  <Loading label="Запрашиваем состояние брони…" />
                ) : null}

                {loaded.kind === "missing" ? (
                  <div className="warn" role="status">
                    Сервер не знает эту бронь или не принимает сохранённый код доступа. Возможно,
                    база была пересоздана.
                  </div>
                ) : null}

                {loaded.kind === "error" ? (
                  <div className="err" role="alert">
                    <span>{describeError(loaded.error).description}</span>
                    <button className="out" type="button" onClick={() => void refresh(item)}>
                      Повторить
                    </button>
                  </div>
                ) : null}

                {actionError[item.id] ? <InlineError error={actionError[item.id]} /> : null}

                {confirming === item.id ? (
                  <div className="warn" role="alertdialog" aria-label={`Отмена брони №${item.id}`}>
                    <b>Отменить бронь №{item.id}?</b>
                    <span>
                      {state?.status === "CONFIRMED"
                        ? "Для оплаченной брони полный возврат возможен не позднее чем за два дня до заезда. Позже бронь отменяется без возврата."
                        : "Бронь ещё не оплачена, поэтому отмена проходит без возврата."}{" "}
                      Действие необратимо: номер снова станет доступен другим гостям.
                    </span>
                    <div className="actions">
                      <button
                        className="out danger"
                        type="button"
                        disabled={working}
                        onClick={() => void cancel(item)}
                      >
                        {working ? "Отменяем…" : "Да, отменить"}
                      </button>
                      <button className="out" type="button" onClick={() => setConfirming(null)}>
                        Оставить бронь
                      </button>
                    </div>
                  </div>
                ) : null}

                <div className="actions">
                  {state?.status === "PENDING" ? (
                    <>
                      <button
                        className="btn"
                        type="button"
                        disabled={working}
                        onClick={() => void pay(item, "SUCCEEDED")}
                      >
                        {working ? "Обрабатываем…" : "Оплатить (demo)"}
                      </button>
                      <button
                        className="out"
                        type="button"
                        disabled={working}
                        onClick={() => void pay(item, "FAILED")}
                        title="Демонстрация неуспешного платежа: бронь остаётся в статусе ожидания"
                      >
                        Отказ платежа
                      </button>
                    </>
                  ) : null}

                  {state && state.status !== "CANCELLED" ? (
                    <button
                      className="out danger"
                      type="button"
                      disabled={working || confirming === item.id}
                      onClick={() => setConfirming(item.id)}
                    >
                      Отменить бронь
                    </button>
                  ) : null}

                  {state ? (
                    <button
                      className="out"
                      type="button"
                      disabled={working}
                      onClick={() => void refresh(item)}
                    >
                      Обновить
                    </button>
                  ) : null}

                  {state?.status === "CANCELLED" || loaded.kind === "missing" ? (
                    <button className="out" type="button" onClick={() => forget(item.id)}>
                      Убрать из списка
                    </button>
                  ) : null}
                </div>

                <details>
                  <summary className="mut" style={{ cursor: "pointer", minHeight: 44 }}>
                    Код доступа к брони
                  </summary>
                  <code className="token">{item.token}</code>
                </details>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}
