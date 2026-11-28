import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { RoomCard } from "../components/RoomCard";
import { SearchForm } from "../components/SearchForm";
import { Empty, ErrorState, RoomSkeletons } from "../components/States";
import { formatDateRange, nightsBetween, nightsLabel, plural } from "../lib/format";
import { stayFromParams, stayToParams, toStay } from "../lib/stay";
import type { StayDraft } from "../lib/stay";
import { useAsync } from "../lib/useAsync";

export function SearchPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState<StayDraft>(() => stayFromParams(params));

  // The teaser list is live availability for the dates currently in the form.
  const preview = useAsync(
    (signal) => api.searchRooms(toStay(draft), signal),
    [draft.check_in, draft.check_out, draft.guests],
  );

  const search = stayToParams(draft).toString();

  return (
    <>
      <h1>Найдите номер у моря</h1>
      <p className="lead">
        Выберите даты и количество гостей — покажем номера, свободные на весь срок. День выезда не
        занимает ночь, поэтому вы платите только за проведённые ночи.
      </p>

      <div className="hero">
        <img src="/images/hero.svg" alt="Корпус отеля «Морской бриз» на берегу" />
      </div>

      <SearchForm
        value={draft}
        onChange={setDraft}
        onSubmit={(next) => navigate(`/rooms?${stayToParams(next).toString()}`)}
        pending={preview.loading}
      />

      <h2>Свободно на {formatDateRange(draft.check_in, draft.check_out)}</h2>

      {preview.loading ? (
        <RoomSkeletons count={3} />
      ) : preview.error ? (
        <ErrorState error={preview.error} onRetry={preview.reload} />
      ) : preview.data && preview.data.length > 0 ? (
        <>
          <p className="mut">
            Найдено {preview.data.length}{" "}
            {plural(preview.data.length, "номер", "номера", "номеров")} ·{" "}
            {nightsLabel(nightsBetween(draft.check_in, draft.check_out))}
          </p>
          <div className="grid">
            {preview.data.slice(0, 3).map((room) => (
              <RoomCard key={room.id} room={room} search={search} />
            ))}
          </div>
        </>
      ) : (
        <Empty
          title="На эти даты свободных номеров нет"
          description="Попробуйте сдвинуть даты или уменьшить количество гостей."
        />
      )}
    </>
  );
}
