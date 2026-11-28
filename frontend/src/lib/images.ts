/**
 * The catalogue has no photo column, so each room gets a stable set of the
 * bundled illustrations. Rotating by room id keeps cards visually distinct.
 */

export interface RoomPhoto {
  src: string;
  caption: string;
}

const POOL: RoomPhoto[] = [
  { src: "/images/room-sea.svg", caption: "Вид из номера" },
  { src: "/images/room-interior.svg", caption: "Интерьер" },
  { src: "/images/room-terrace.svg", caption: "Терраса на закате" },
  { src: "/images/room-bath.svg", caption: "Ванная комната" },
];

const GALLERY_SIZE = 3;

export function roomGallery(roomId: number): RoomPhoto[] {
  const offset = ((roomId % POOL.length) + POOL.length) % POOL.length;
  return Array.from({ length: GALLERY_SIZE }, (_, index) => POOL[(offset + index) % POOL.length]);
}

export function roomCover(roomId: number): RoomPhoto {
  return roomGallery(roomId)[0];
}
