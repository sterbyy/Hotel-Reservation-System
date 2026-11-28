/** Mirrors app/schemas.py. Decimals arrive as strings with two decimal places. */

export type BookingStatus = "PENDING" | "CONFIRMED" | "CANCELLED";
export type PaymentStatus = "FAILED" | "SUCCEEDED" | "REFUNDED";
export type DemoPaymentOutcome = "SUCCEEDED" | "FAILED";

export interface RoomSummary {
  id: number;
  name: string;
  category: string;
  capacity: number;
  nightly_rate: string;
}

export interface RoomDetails extends RoomSummary {
  description: string;
  amenities: string[];
}

export interface Stay {
  check_in: string;
  check_out: string;
  guests: number;
}

export interface BookingCreate extends Stay {
  room_id: number;
}

export interface Payment {
  status: PaymentStatus;
  refunded_amount: string | null;
}

export interface Booking {
  id: number;
  room_id: number;
  status: BookingStatus;
  check_in: string;
  check_out: string;
  guests: number;
  total_price: string;
}

export interface BookingState extends Booking {
  payment: Payment | null;
}

export interface BookingCreated extends Booking {
  access_token: string;
}
