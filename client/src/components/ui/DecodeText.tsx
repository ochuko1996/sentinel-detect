"use client";

import { useEffect, useRef, useState } from "react";

const GLYPHS = "!<>-_\\/[]{}—=+*^?#________";

/**
 * Scrambles through random glyphs before settling on the real text —
 * the "decrypting a redacted field" effect used for major headings.
 * Runs once on mount; respects prefers-reduced-motion.
 */
export function DecodeText({
  text,
  className,
  speed = 28,
}: {
  text: string;
  className?: string;
  speed?: number;
}) {
  const [display, setDisplay] = useState(text);
  const frame = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setDisplay(text);
      return;
    }

    let iteration = 0;
    const totalFrames = text.length * 2;

    const tick = () => {
      iteration += 1;
      const revealCount = Math.floor((iteration / totalFrames) * text.length);
      setDisplay(
        text
          .split("")
          .map((char, index) => {
            if (char === " ") return " ";
            if (index < revealCount) return text[index];
            return GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
          })
          .join(""),
      );

      if (iteration < totalFrames) {
        frame.current = setTimeout(tick, speed);
      } else {
        setDisplay(text);
      }
    };

    tick();
    return () => clearTimeout(frame.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  return <span className={className}>{display}</span>;
}
