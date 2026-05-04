"use client";
import { motion, useScroll, useTransform } from "motion/react";

/**
 * Wraps the site header in a sticky container that transitions from
 * transparent → frosted-glass as the user scrolls down.
 */
export function StickyNav({ children }) {
  const { scrollY } = useScroll();

  const bg = useTransform(
    scrollY,
    [0, 72],
    ["rgba(248,246,242,0)", "rgba(248,246,242,0.88)"]
  );
  const borderColor = useTransform(
    scrollY,
    [0, 72],
    ["rgba(31,29,30,0)", "rgba(31,29,30,0.12)"]
  );
  const shadow = useTransform(
    scrollY,
    [0, 72],
    ["0 0 0 rgba(0,0,0,0)", "0 2px 24px rgba(84,62,48,0.07)"]
  );

  return (
    <motion.div
      className="sticky-nav"
      style={{
        backgroundColor: bg,
        boxShadow: shadow,
        borderBottom: "1px solid",
        borderColor,
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
      }}
    >
      {children}
    </motion.div>
  );
}
