import type {
  BookingCreate,
  BookingCreated,
  BookingState,
  DemoPaymentOutcome,
  RoomDetails,
  RoomSummary,
  Stay,
} from "./types";

/** Empty by default so the Vite dev proxy keeps the browser on one origin. */
const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

/** Public header name from app/api/bookings.py. */
const TOKEN_HEADER = "X-Booking-Access-Token";

interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** A failed API call, carrying the HTTP status so screens can react to 404/409. */
export class ApiError extends Error {
  readonly status: number;
  readonly issues: ValidationIssue[];

  constructor(status: number, message: string, issues: ValidationIssue[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.issues = issues;
  }
}

/** Raised when the browser could not reach the backend at all. */
export class NetworkError extends Error {
  constructor() {
    super("Не удалось связаться с сервером. Проверьте, что backend запущен.");
    this.name = "NetworkError";
  }
}

const FALLBACK: Record<number, string> = {
  400: "Запрос отклонён сервером.",
  404: "Запрошенные данные не найдены.",
  409: "Данные изменились: повторите действие.",
  422: "Проверьте введённые значения.",
  500: "Внутренняя ошибка сервера.",
  503: "База данных недоступна. Попробуйте позже.",
};

/** The backend answers with either {detail: string} or {detail: ValidationIssue[]}. */
async function readError(response: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail;
  } catch {
    detail = undefined;
  }
  if (typeof detail === "string" && detail) {
    return new ApiError(response.status, detail);
  }
  if (Array.isArray(detail)) {
    const issues = detail as ValidationIssue[];
    const first = issues[0];
    const message = first
      ? `${first.loc.slice(1).join(".") || "запрос"}: ${first.msg}`
      : FALLBACK[422];
    return new ApiError(response.status, message, issues);
  }
  return new ApiError(
    response.status,
    FALLBACK[response.status] ?? `Ошибка сервера (${response.status}).`,
  );
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  token?: string;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, signal } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers[TOKEN_HEADER] = token;
  }

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new NetworkError();
  }

  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as T;
}

function stayQuery(stay: Stay): string {
  return new URLSearchParams({
    check_in: stay.check_in,
    check_out: stay.check_out,
    guests: String(stay.guests),
  }).toString();
}

export const api = {
  health: (signal?: AbortSignal) => request<{ status: "ok" }>("/health", { signal }),

  searchRooms: (stay: Stay, signal?: AbortSignal) =>
    request<RoomSummary[]>(`/api/rooms/search?${stayQuery(stay)}`, { signal }),

  roomDetails: (roomId: number, signal?: AbortSignal) =>
    request<RoomDetails>(`/api/rooms/${roomId}`, { signal }),

  createBooking: (booking: BookingCreate) =>
    request<BookingCreated>("/api/bookings", { method: "POST", body: booking }),

  getBooking: (bookingId: number, token: string, signal?: AbortSignal) =>
    request<BookingState>(`/api/bookings/${bookingId}`, { token, signal }),

  payBooking: (bookingId: number, token: string, outcome: DemoPaymentOutcome) =>
    request<BookingState>(`/api/bookings/${bookingId}/payment`, {
      method: "POST",
      body: { outcome },
      token,
    }),

  cancelBooking: (bookingId: number, token: string) =>
    request<BookingState>(`/api/bookings/${bookingId}/cancel`, { method: "POST", token }),
};
