import { nightsBetween, parseIsoDate, todayIso } from "./format";
import type { Stay } from "../api/types";

export const MAX_GUESTS = 10;
export const MAX_NIGHTS = 60;

export type StayErrors = Partial<Record<"check_in" | "check_out" | "guests", string>>;

export interface StayDraft {
  check_in: string;
  check_out: string;
  guests: string;
}

/**
 * Client-side mirror of the Stay rules in app/schemas.py: real calendar dates,
 * check_out strictly later than check_in, and a positive guest count.
 */
export function validateStay(draft: StayDraft): StayErrors {
  const errors: StayErrors = {};
  const checkIn = parseIsoDate(draft.check_in);
  const checkOut = parseIsoDate(draft.check_out);

  if (!draft.check_in) {
    errors.check_in = "Укажите дату заезда.";
  } else if (!checkIn) {
    errors.check_in = "Введите существующую дату в формате ГГГГ-ММ-ДД.";
  } else if (draft.check_in < todayIso()) {
    errors.check_in = "Дата заезда не может быть в прошлом.";
  }

  if (!draft.check_out) {
    errors.check_out = "Укажите дату выезда.";
  } else if (!checkOut) {
    errors.check_out = "Введите существующую дату в формате ГГГГ-ММ-ДД.";
  } else if (checkIn && draft.check_out <= draft.check_in) {
    errors.check_out = "Выезд должен быть позже заезда.";
  } else if (checkIn && nightsBetween(draft.check_in, draft.check_out) > MAX_NIGHTS) {
    errors.check_out = `Срок брони не превышает ${MAX_NIGHTS} ночей.`;
  }

  const guests = Number(draft.guests);
  if (draft.guests.trim() === "") {
    errors.guests = "Укажите количество гостей.";
  } else if (!Number.isInteger(guests) || guests < 1) {
    errors.guests = "Гостей должно быть не меньше одного.";
  } else if (guests > MAX_GUESTS) {
    errors.guests = `Для группы больше ${MAX_GUESTS} гостей свяжитесь с отелем.`;
  }

  return errors;
}

export function hasErrors(errors: StayErrors): boolean {
  return Object.keys(errors).length > 0;
}

export function toStay(draft: StayDraft): Stay {
  return {
    check_in: draft.check_in,
    check_out: draft.check_out,
    guests: Number(draft.guests),
  };
}

export function toDraft(stay: Stay): StayDraft {
  return {
    check_in: stay.check_in,
    check_out: stay.check_out,
    guests: String(stay.guests),
  };
}

/** Reads a stay from the URL, falling back to a three-night stay starting in three days. */
export function stayFromParams(params: URLSearchParams): StayDraft {
  const today = parseIsoDate(todayIso()) ?? new Date();
  const defaultIn = new Date(today);
  defaultIn.setDate(defaultIn.getDate() + 3);
  const defaultOut = new Date(defaultIn);
  defaultOut.setDate(defaultOut.getDate() + 3);
  const iso = (date: Date) =>
    `${date.getFullYear()}-${`${date.getMonth() + 1}`.padStart(2, "0")}-${`${date.getDate()}`.padStart(2, "0")}`;

  return {
    check_in: params.get("check_in") ?? iso(defaultIn),
    check_out: params.get("check_out") ?? iso(defaultOut),
    guests: params.get("guests") ?? "2",
  };
}

export function stayToParams(draft: StayDraft): URLSearchParams {
  return new URLSearchParams({
    check_in: draft.check_in,
    check_out: draft.check_out,
    guests: draft.guests,
  });
}
