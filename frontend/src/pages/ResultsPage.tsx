import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { RoomCard } from "../components/RoomCard";
import { SearchForm } from "../components/SearchForm";
import { Empty, ErrorState, RoomSkeletons } from "../components/States";
import {
  categoryLabel,
  formatDateRange,
  guestsLabel,
  nightsBetween,
  nightsLabel,
  plural,
} from "../lib/format";
import { stayFromParams, stayToParams, toStay } from "../lib/stay";
import type { StayDraft } from "../lib/stay";
import { useAsync } from "../lib/useAsync";

export function ResultsPage() {
  const [params, setParams] = useSearchParams();
  const stay = stayFromParams(params);
  const [draft, setDraft] = useState<StayDraft>(stay);
  const [editing, setEditing] = useState(false);
  const [maxPrice, setMaxPrice] = useState("");
  const [categories, setCategories] = useState<string[]>([]);

  const rooms = useAsync(
    (signal) => api.searchRooms(toStay(stay), signal),
    [stay.check_in, stay.check_out, stay.guests],
  );

  const search = stayToParams(stay).toString();
  const nights = nightsBetween(stay.check_in, stay.check_out);

  // Filters narrow the list the API returned; availability itself stays server-side.
  const available = rooms.data ?? [];
  const allCategories = useMemo(
    () => [...new Set(available.map((room) => room.category))].sort(),
    [available],
  );
  const limit = Number(maxPrice);
  const visible = available.filter((room) => {
    const withinPrice = !maxPrice.trim() || !Number.isFinite(limit) || Number(room.nightly_rate) <= limit;
    const withinCategory = categories.length === 0 || categories.includes(room.category);
    return withinPrice && withinCategory;
  });

  function toggleCategory(category: string) {
    setCategories((current) =>
      current.includes(category)
        ? current.filter((item) => item !== category)
        : [...current, category],
    );
  }

  const filtersActive = maxPrice.trim() !== "" || categories.length > 0;

  return (
    <>
      <div className="bar">
        <div>
          <b>Сочи, Морской бриз</b> · {formatDateRange(stay.check_in, stay.check_out)} ·{" "}
          {guestsLabel(Number(stay.guests))} · {nightsLabel(nights)}
        </div>
        <button className="out" type="button" onClick={() => setEditing((value) => !value)}>
          {editing ? "Скрыть форму" : "Изменить поиск"}
        </button>
      </div>

      {editing ? (
        <div style={{ marginBottom: 24 }}>
          <SearchForm
            value={draft}
            onChange={setDraft}
            submitLabel="Обновить"
            pending={rooms.loading}
            onSubmit={(next) => {
              setParams(stayToParams(next));
              setEditing(false);
            }}
          />
        </div>
      ) : null}

      <div className="res">
        <aside className="fl">
          <b>Фильтры</b>
          <label className="f">
            Цена до, {"₸"} за ночь
            <input
              type="number"
              inputMode="numeric"
              min={0}
              step={500}
              placeholder="без ограничения"
              value={maxPrice}
              onChange={(event) => setMaxPrice(event.target.value)}
            />
          </label>

          <div>
            <div className="mut" style={{ marginBottom: 4 }}>
              Категория
            </div>
            {allCategories.length > 0 ? (
              allCategories.map((category) => (
                <label className="chk" key={category}>
                  <input
                    type="checkbox"
                    checked={categories.includes(category)}
                    onChange={() => toggleCategory(category)}
                  />
                  {categoryLabel(category)}
                </label>
              ))
            ) : (
              <span className="mut">Нет доступных категорий</span>
            )}
          </div>

          <button
            className="out"
            type="button"
            disabled={!filtersActive}
            onClick={() => {
              setMaxPrice("");
              setCategories([]);
            }}
          >
            Сбросить фильтры
          </button>
        </aside>

        <div className="list">
          {rooms.loading ? (
            <RoomSkeletons count={3} />
          ) : rooms.error ? (
            <ErrorState error={rooms.error} onRetry={rooms.reload} />
          ) : available.length === 0 ? (
            <Empty
              title="Свободных номеров нет"
              description="На выбранные даты все подходящие номера заняты. Измените даты или уменьшите количество гостей."
            >
              <button className="out" type="button" onClick={() => setEditing(true)}>
                Изменить поиск
              </button>
            </Empty>
          ) : visible.length === 0 ? (
            <Empty
              title="Фильтры ничего не нашли"
              description="Свободные номера есть, но ни один не подходит под выбранные фильтры."
            >
              <button
                className="out"
                type="button"
                onClick={() => {
                  setMaxPrice("");
                  setCategories([]);
                }}
              >
                Сбросить фильтры
              </button>
            </Empty>
          ) : (
            <>
              <div className="mut" aria-live="polite">
                Найдено {visible.length} {plural(visible.length, "номер", "номера", "номеров")} из{" "}
                {available.length} свободных
              </div>
              {visible.map((room) => (
                <RoomCard key={room.id} room={room} search={search} layout="row" />
              ))}
            </>
          )}

          <p className="mut">
            Уже бронировали? <Link to="/bookings">Откройте свои брони</Link>.
          </p>
        </div>
      </div>
    </>
  );
}
