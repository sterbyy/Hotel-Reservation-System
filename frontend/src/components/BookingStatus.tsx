import type { BookingStatus, PaymentStatus } from "../api/types";

const BOOKING_LABELS: Record<BookingStatus, string> = {
  PENDING: "Ожидает оплаты",
  CONFIRMED: "Подтверждена",
  CANCELLED: "Отменена",
};

const PAYMENT_LABELS: Record<PaymentStatus, string> = {
  SUCCEEDED: "Оплата прошла",
  FAILED: "Оплата не прошла",
  REFUNDED: "Возврат выполнен",
};

export function StatusPill({ status }: { status: BookingStatus }) {
  return <span className={`pill ${status.toLowerCase()}`}>{BOOKING_LABELS[status]}</span>;
}

export function bookingStatusLabel(status: BookingStatus): string {
  return BOOKING_LABELS[status];
}

export function paymentStatusLabel(status: PaymentStatus): string {
  return PAYMENT_LABELS[status];
}
