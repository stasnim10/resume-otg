"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

const appUrl =
  process.env.NEXT_PUBLIC_APP_URL || "https://resume-optimizer-otg.streamlit.app";

const ease: [number, number, number, number] = [0.16, 1, 0.3, 1];

function AnimatedHero() {
  const [titleNumber, setTitleNumber] = useState(0);

  const titles = useMemo(
    () => ["targeted", "optimized", "tailored", "ATS-ready", "stronger"],
    []
  );

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setTitleNumber((prev) => (prev === titles.length - 1 ? 0 : prev + 1));
    }, 2200);
    return () => clearTimeout(timeoutId);
  }, [titleNumber, titles]);

  return (
    <div className="w-full" style={{ fontFamily: "var(--font-jakarta, var(--font-body))" }}>
      <div className="container mx-auto">
        <div className="flex gap-8 py-20 lg:py-36 items-center justify-center flex-col">

          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease }}
          >
            <Button variant="secondary" size="sm" className="gap-3 rounded-full px-4">
              <Sparkles className="w-3.5 h-3.5" />
              Free to use — no account required
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </motion.div>

          {/* Headline + animated word */}
          <div className="flex gap-3 flex-col items-center">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.65, delay: 0.1, ease }}
              className="text-5xl md:text-7xl max-w-3xl tracking-tighter text-center font-semibold"
              style={{ fontFamily: "var(--font-display, serif)", letterSpacing: "-0.03em" }}
            >
              <span className="text-spektr-cyan-50">Your resume,</span>

              {/* Animated rotating word */}
              <span className="relative flex w-full justify-center overflow-hidden text-center md:pb-4 md:pt-1">
                &nbsp;
                {titles.map((title, index) => (
                  <motion.span
                    key={index}
                    className="absolute font-semibold"
                    style={{ color: "var(--accent)" }}
                    initial={{ opacity: 0, y: "-100%" }}
                    transition={{ type: "spring", stiffness: 50 }}
                    animate={
                      titleNumber === index
                        ? { y: 0, opacity: 1 }
                        : {
                            y: titleNumber > index ? "-150%" : "150%",
                            opacity: 0,
                          }
                    }
                  >
                    {title}
                  </motion.span>
                ))}
              </span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.22, ease }}
              className="text-lg md:text-xl leading-relaxed tracking-tight text-muted-foreground max-w-2xl text-center"
            >
              Resume Builder OTG turns your resume and job descriptions into cleaner, more
              targeted applications — with guided onboarding, explainable AI edits, and a
              review flow you stay in control of every step of the way.
            </motion.p>
          </div>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.34, ease }}
            className="flex flex-row gap-3 flex-wrap justify-center"
          >
            <Button
              size="lg"
              className="gap-3 rounded-full px-7 font-semibold"
              asChild
            >
              <a href={appUrl} target="_blank" rel="noreferrer">
                Start optimizing <ArrowRight className="w-4 h-4" />
              </a>
            </Button>
            <Button
              size="lg"
              className="gap-3 rounded-full px-7 font-semibold"
              variant="outline"
              asChild
            >
              <a href="#how-it-works">
                See how it works
              </a>
            </Button>
          </motion.div>

          {/* Trust signals */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.48, ease }}
            className="flex flex-wrap gap-2 justify-center"
          >
            {[
              "Guided onboarding",
              "Review before export",
              "Job Tracker included",
              "Private AI mode available",
            ].map((signal) => (
              <span
                key={signal}
                className="text-xs text-muted-foreground border border-border rounded-full px-3 py-1.5"
                style={{ background: "rgba(255,255,255,0.5)" }}
              >
                {signal}
              </span>
            ))}
          </motion.div>

        </div>
      </div>
    </div>
  );
}

export { AnimatedHero };
