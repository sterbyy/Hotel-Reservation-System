/**
 * The API issues a booking access token once, at creation, and has no account
 * recovery (see "Ограничения прототипа" in README.md). The guest's own browser is
 * therefore the only place the token can live, so bookings made here are kept in
 * localStorage and re-read from the API on every visit.
 */

const KEY = "hotel.bookings.v1";

export interface SavedBooking {
  id: number;
  token: string;
  roomId: number;
  roomName: string;
  checkIn: string;
  checkOut: string;
  guests: number;
  totalPrice: string;
  savedAt: string;
}

function isSaved(value: unknown): value is SavedBooking {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    typeof item.id === "number" &&
    typeof item.token === "string" &&
    typeof item.roomId === "number" &&
    typeof item.roomName === "string" &&
    typeof item.checkIn === "string" &&
    typeof item.checkOut === "string" &&
    typeof item.guests === "number" &&
    typeof item.totalPrice === "string"
  );
}

export function loadBookings(): SavedBooking[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isSaved) : [];
  } catch {
    return [];
  }
}

function write(bookings: SavedBooking[]): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(bookings));
  } catch {
    // Private-mode or blocked storage: the booking still exists on the server,
    // and the confirmation screen shows the id and token for the guest to copy.
  }
}

export function saveBooking(booking: SavedBooking): SavedBooking[] {
  const rest = loadBookings().filter((item) => item.id !== booking.id);
  const next = [booking, ...rest];
  write(next);
  return next;
}

/** Forgets a booking locally. The booking itself stays on the server. */
export function forgetBooking(id: number): SavedBooking[] {
  const next = loadBookings().filter((item) => item.id !== id);
  write(next);
  return next;
}

export function findBooking(id: number): SavedBooking | undefined {
  return loadBookings().find((item) => item.id === id);
}
