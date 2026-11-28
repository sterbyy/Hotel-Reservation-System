import { useState } from "react";
import type { RoomPhoto } from "../lib/images";

/** Main photo with prev/next controls and thumbnails, as in the mockup. */
export function Gallery({ photos, roomName }: { photos: RoomPhoto[]; roomName: string }) {
  const [index, setIndex] = useState(0);
  const current = photos[index] ?? photos[0];
  const step = (delta: number) => setIndex((photos.length + index + delta) % photos.length);

  return (
    <>
      <div className="big">
        <img src={current.src} alt={`${roomName}: ${current.caption.toLowerCase()}`} />
        <span className="tag">
          {current.caption} · фото {index + 1} из {photos.length}
        </span>
        <div className="arrows">
          <button type="button" aria-label="Предыдущее фото" onClick={() => step(-1)}>
            ‹
          </button>
          <button type="button" aria-label="Следующее фото" onClick={() => step(1)}>
            ›
          </button>
        </div>
      </div>
      <div className="th">
        {photos.map((photo, position) => (
          <button
            key={`${photo.src}-${position}`}
            type="button"
            aria-current={position === index}
            aria-label={`Показать фото ${position + 1}: ${photo.caption}`}
            onClick={() => setIndex(position)}
          >
            <img src={photo.src} alt="" loading="lazy" />
          </button>
        ))}
      </div>
    </>
  );
}
