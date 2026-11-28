import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { BookingsPage } from "./pages/BookingsPage";
import { Empty } from "./components/States";
import { ResultsPage } from "./pages/ResultsPage";
import { RoomPage } from "./pages/RoomPage";
import { SearchPage } from "./pages/SearchPage";
import { Link } from "react-router-dom";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export function App() {
  return (
    <>
      <ScrollToTop />
      <header className="app">
        <NavLink to="/" className="logo">
          Морской бриз
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Поиск
          </NavLink>
          <NavLink to="/rooms">Номера</NavLink>
          <NavLink to="/bookings">Мои брони</NavLink>
        </nav>
      </header>

      <main className="wrap">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/rooms" element={<ResultsPage />} />
          <Route path="/rooms/:roomId" element={<RoomPage />} />
          <Route path="/bookings" element={<BookingsPage />} />
          <Route path="/index.html" element={<Navigate to="/" replace />} />
          <Route
            path="*"
            element={
              <Empty title="Страница не найдена" description="Проверьте адрес или начните с поиска.">
                <Link className="btn" to="/">
                  На главную
                </Link>
              </Empty>
            }
          />
        </Routes>
      </main>

      <footer className="app">
        Прототип системы бронирования. Оплата и возврат демонстрационные, деньги не списываются.
      </footer>
    </>
  );
}
