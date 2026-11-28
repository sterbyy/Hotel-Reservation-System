import type { ReactNode } from "react";
import { ApiError, NetworkError } from "../api/client";

export function Loading({ label = "Загружаем данные…" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="spinner" />
      <p>{label}</p>
    </div>
  );
}

export function RoomSkeletons({ count = 3 }: { count?: number }) {
  return (
    <div className="list" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="skeleton sk-row" />
      ))}
    </div>
  );
}

export function Empty({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="state">
      <h3>{title}</h3>
      <p>{description}</p>
      {children}
    </div>
  );
}

/** Turns an unknown rejection into a message plus a hint about what to do next. */
export function describeError(error: unknown): { title: string; description: string } {
  if (error instanceof NetworkError) {
    return {
      title: "Сервер недоступен",
      description:
        "Не удалось связаться с backend. Убедитесь, что uvicorn запущен на http://127.0.0.1:8000, и повторите попытку.",
    };
  }
  if (error instanceof ApiError) {
    if (error.status === 503) {
      return {
        title: "База данных недоступна",
        description:
          "Backend отвечает, но не может обратиться к PostgreSQL. Проверьте подключение в .env и повторите попытку.",
      };
    }
    if (error.status >= 500) {
      return { title: "Ошибка сервера", description: error.message };
    }
    return { title: "Запрос не выполнен", description: error.message };
  }
  return {
    title: "Непредвиденная ошибка",
    description: error instanceof Error ? error.message : "Повторите попытку позже.",
  };
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { title, description } = describeError(error);
  return (
    <div className="state" role="alert">
      <h3>{title}</h3>
      <p>{description}</p>
      {onRetry ? (
        <button className="out" type="button" onClick={onRetry}>
          Повторить
        </button>
      ) : null}
    </div>
  );
}

export function InlineError({ error }: { error: unknown }) {
  const { description } = describeError(error);
  return (
    <div className="err" role="alert">
      <span>{description}</span>
    </div>
  );
}
