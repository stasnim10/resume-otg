"use client";
import { useRef } from "react";
import { motion, useInView } from "motion/react";

const ease = [0.16, 1, 0.3, 1];

/**
 * Fade-up reveal triggered when the element enters the viewport.
 * @param {object} props
 * @param {React.ReactNode} props.children
 * @param {number} [props.delay=0]
 * @param {number} [props.distance=28]
 * @param {string} [props.className]
 */
export function Reveal({ children, delay = 0, distance = 28, className }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-72px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: distance }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.62, delay, ease }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
