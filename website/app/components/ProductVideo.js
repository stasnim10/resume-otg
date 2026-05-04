"use client";

import Image from "next/image";
import { useState } from "react";

const videoId = "W7k3avzYMB4";

export function ProductVideo() {
  const [playing, setPlaying] = useState(false);

  return (
    <div className="video-frame">
      {playing ? (
        <iframe
          src={`https://www.youtube.com/embed/${videoId}?autoplay=1`}
          title="Resume OTG product walkthrough"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          referrerPolicy="strict-origin-when-cross-origin"
          allowFullScreen
        />
      ) : (
        <button
          className="video-poster"
          type="button"
          onClick={() => setPlaying(true)}
          aria-label="Play Resume OTG product walkthrough"
        >
          <Image
            src={`https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`}
            alt=""
            fill
            sizes="(max-width: 1180px) 100vw, 1180px"
            unoptimized
          />
          <span className="play-icon" aria-hidden="true">
            Play
          </span>
        </button>
      )}
    </div>
  );
}
