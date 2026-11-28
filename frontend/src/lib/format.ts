/** Prototype currency is KZT (see docs/API_CONTRACT.md); the API has no currency field. */
export const CURRENCY = "₸";

const money = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const dayMonth = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
const fullDate = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

/** Decimal strings from the API are formatted without losing the stored precision. */
export function formatMoney(value: string | number): string {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) {
    return `${value} ${CURRENCY}`;
  }
  return `${money.format(amount)} ${CURRENCY}`;
}

/** Multiplies a decimal rate string by the night count using integer tiyn. */
export function multiplyRate(rate: string, nights: number): string {
  const [whole, fraction = ""] = rate.split(".");
  const minorUnits = BigInt(`${whole}${fraction.padEnd(2, "0").slice(0, 2)}`);
  const total = minorUnits * BigInt(nights);
  const sign = total < 0n ? "-" : "";
  const digits = (total < 0n ? -total : total).toString().padStart(3, "0");
  return `${sign}${digits.slice(0, -2)}.${digits.slice(-2)}`;
}

/** Parses an ISO calendar date as a local midnight so day arithmetic stays stable. */
export function parseIsoDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return null;
  }
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const valid =
    date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
  return valid ? date : null;
}

export function toIsoDate(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function todayIso(): string {
  return toIsoDate(new Date());
}

export function addDaysIso(value: string, days: number): string {
  const date = parseIsoDate(value);
  if (!date) {
    return value;
  }
  date.setDate(date.getDate() + days);
  return toIsoDate(date);
}

/** The check-out date is excluded from the stay, so nights is a plain day difference. */
export function nightsBetween(checkIn: string, checkOut: string): number {
  const from = parseIsoDate(checkIn);
  const to = parseIsoDate(checkOut);
  if (!from || !to) {
    return 0;
  }
  return Math.round((to.getTime() - from.getTime()) / 86_400_000);
}

export function formatDateRange(checkIn: string, checkOut: string): string {
  const from = parseIsoDate(checkIn);
  const to = parseIsoDate(checkOut);
  if (!from || !to) {
    return `${checkIn} — ${checkOut}`;
  }
  return `${dayMonth.format(from)} — ${dayMonth.format(to)}`;
}

export function formatFullDate(value: string): string {
  const date = parseIsoDate(value);
  return date ? fullDate.format(date) : value;
}

/** Russian plural forms, e.g. 1 ночь / 2 ночи / 5 ночей. */
export function plural(count: number, one: string, few: string, many: string): string {
  const mod100 = Math.abs(count) % 100;
  const mod10 = mod100 % 10;
  if (mod100 >= 11 && mod100 <= 14) {
    return many;
  }
  if (mod10 === 1) {
    return one;
  }
  if (mod10 >= 2 && mod10 <= 4) {
    return few;
  }
  return many;
}

export function nightsLabel(count: number): string {
  return `${count} ${plural(count, "ночь", "ночи", "ночей")}`;
}

export function guestsLabel(count: number): string {
  return `${count} ${plural(count, "гость", "гостя", "гостей")}`;
}

/** Genitive form for phrases like «до 2 гостей» and «не больше 4 гостей». */
export function guestsGenitive(count: number): string {
  return `${count} ${plural(count, "гостя", "гостей", "гостей")}`;
}

const CATEGORIES: Record<string, string> = {
  standard: "Стандарт",
  family: "Семейный",
  comfort: "Комфорт",
  deluxe: "Люкс",
  suite: "Люкс",
};

export function categoryLabel(category: string): string {
  return CATEGORIES[category.toLowerCase()] ?? category;
}
