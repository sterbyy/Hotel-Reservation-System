import { useId, useState } from "react";
import { addDaysIso, todayIso } from "../lib/format";
import { MAX_GUESTS, hasErrors, validateStay } from "../lib/stay";
import type { StayDraft, StayErrors } from "../lib/stay";

interface Props {
  value: StayDraft;
  onChange: (next: StayDraft) => void;
  onSubmit: (draft: StayDraft) => void;
  submitLabel?: string;
  pending?: boolean;
}

/** The search panel from the mockup: destination, dates, guests and one action. */
export function SearchForm({
  value,
  onChange,
  onSubmit,
  submitLabel = "Найти",
  pending = false,
}: Props) {
  const ids = useId();
  const [touched, setTouched] = useState(false);
  const errors: StayErrors = validateStay(value);
  const shown: StayErrors = touched ? errors : {};

  function patch(part: Partial<StayDraft>) {
    const next = { ...value, ...part };
    // Keep the stay valid while the guest moves the arrival date forward.
    if (part.check_in && next.check_out <= next.check_in) {
      next.check_out = addDaysIso(next.check_in, 1);
    }
    onChange(next);
  }

  return (
    <form
      className="search"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        setTouched(true);
        if (!hasErrors(errors)) {
          onSubmit(value);
        }
      }}
    >
      <label className="f" style={{ flex: "2 1 220px" }} htmlFor={`${ids}-place`}>
        Город или отель
        <input
          id={`${ids}-place`}
          type="text"
          value="Сочи, Морской бриз"
          readOnly
          aria-describedby={`${ids}-place-note`}
        />
        <span id={`${ids}-place-note`} className="mut" style={{ fontSize: 12 }}>
          В прототипе доступен один отель
        </span>
      </label>

      <label className="f" htmlFor={`${ids}-in`}>
        Заезд
        <input
          id={`${ids}-in`}
          type="date"
          value={value.check_in}
          min={todayIso()}
          aria-invalid={shown.check_in ? true : undefined}
          onChange={(event) => patch({ check_in: event.target.value })}
        />
        {shown.check_in ? <span className="field-error">{shown.check_in}</span> : null}
      </label>

      <label className="f" htmlFor={`${ids}-out`}>
        Выезд
        <input
          id={`${ids}-out`}
          type="date"
          value={value.check_out}
          min={addDaysIso(value.check_in || todayIso(), 1)}
          aria-invalid={shown.check_out ? true : undefined}
          onChange={(event) => patch({ check_out: event.target.value })}
        />
        {shown.check_out ? <span className="field-error">{shown.check_out}</span> : null}
      </label>

      <label className="f" style={{ flex: "0 1 110px" }} htmlFor={`${ids}-guests`}>
        Гостей
        <input
          id={`${ids}-guests`}
          type="number"
          inputMode="numeric"
          value={value.guests}
          min={1}
          max={MAX_GUESTS}
          step={1}
          aria-invalid={shown.guests ? true : undefined}
          onChange={(event) => patch({ guests: event.target.value })}
        />
        {shown.guests ? <span className="field-error">{shown.guests}</span> : null}
      </label>

      <button className="btn" type="submit" disabled={pending}>
        {pending ? "Ищем…" : submitLabel}
      </button>
    </form>
  );
}
