import { Link } from "react-router-dom";
import type { RoomSummary } from "../api/types";
import { categoryLabel, formatMoney, guestsGenitive } from "../lib/format";
import { roomCover } from "../lib/images";

interface Props {
  room: RoomSummary;
  /** Query string carrying the current stay, so the room page keeps the dates. */
  search: string;
  layout?: "grid" | "row";
}

export function RoomCard({ room, search, layout = "grid" }: Props) {
  const cover = roomCover(room.id);
  const href = `/rooms/${room.id}${search ? `?${search}` : ""}`;

  return (
    <article className={layout === "row" ? "card row" : "card"}>
      <div className="ph">
        <img src={cover.src} alt={`${room.name}: ${cover.caption.toLowerCase()}`} loading="lazy" />
        <span>{categoryLabel(room.category)}</span>
      </div>
      <div className="cb">
        <h3>
          <Link to={href}>{room.name}</Link>
        </h3>
        <div className="mut">
          до {guestsGenitive(room.capacity)} · категория «{categoryLabel(room.category)}»
        </div>
        <div className="end">
          <div className="price">
            {formatMoney(room.nightly_rate)} <small>/ ночь</small>
          </div>
          <Link className="btn" to={href}>
            Выбрать
          </Link>
        </div>
      </div>
    </article>
  );
}
