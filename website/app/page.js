import Image from "next/image";
import { StickyNav } from "./components/StickyNav";
import { ProductVideo } from "./components/ProductVideo";
import { Reveal } from "./components/Reveal";
import { StaggerGrid, StaggerItem } from "./components/StaggerGrid";
import { SupportActions } from "@/components/SupportActions";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://resume-optimizer-otg.streamlit.app";

const steps = [
  {
    step: "01",
    title: "Tell us your goals",
    body: "Share your career stage and target roles so we can tailor the experience to your specific next step.",
  },
  {
    step: "02",
    title: "Import your history",
    body: "Upload your existing resume or LinkedIn profile. We’ll instantly structure your past experience into a clean, workable profile.",
  },
  {
    step: "03",
    title: "Refine the details",
    body: "You are always in control. Review your extracted experience and tweak the narrative before any optimization happens.",
  },
  {
    step: "04",
    title: "Tailor and apply",
    body: "Match your profile to a specific job description. We’ll suggest precise, high-impact changes to help you stand out.",
  },
];

export default function HomePage() {
  return (
    <main className="page-shell">
      <StickyNav>
        <header className="site-header">
          <a className="brand-mark" href="#top">
            <div className="brand-lockup">
              <Image src="/logo.jpeg" alt="Resume OTG logo" width={44} height={44} />
              <div>
                <p className="brand-name">Resume OTG</p>
                <p className="brand-subtitle">Smart resume optimization. No chaos, just clarity.</p>
              </div>
            </div>
          </a>
          <nav className="site-nav">
            <a href="#how-it-works">How it works</a>
            <a href="#product">Product</a>
            <a href="#support">Support</a>
            <a className="nav-cta" href={appUrl} target="_blank" rel="noreferrer">
              Open app
            </a>
          </nav>
        </header>
      </StickyNav>

      <section className="hero-simple" id="top">
        <div className="hero-simple-copy">
          <p className="eyebrow">Resume OTG</p>
          <h1>Craft your perfect resume. Land the interview.</h1>
          <p className="hero-simple-body">
            Stop wrestling with formatting and generic AI rewrites. Resume OTG guides you through a clean, step-by-step process to tailor your experience for the exact roles you want—keeping you in control every step of the way.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href={appUrl} target="_blank" rel="noreferrer">
              Open app
            </a>
            <a className="button button-secondary" href="#how-it-works">
              See how it works
            </a>
          </div>
          <p className="app-load-note">
            The app may take a moment to wake up on first load.
          </p>
        </div>

        <div className="hero-simple-visual">
          <Image
            src="/hero-image.jpeg"
            alt="Resume OTG hero artwork"
            width={2290}
            height={1856}
            className="hero-image"
            priority
            fetchPriority="high"
            decoding="async"
          />
        </div>
      </section>

      <section className="section" id="how-it-works">
        <Reveal className="section-heading narrow">
          <p className="eyebrow">Guided workflow</p>
          <h2>Simple, guided, and review-first.</h2>
        </Reveal>
        <StaggerGrid className="flow-grid">
          {steps.map((item) => (
            <StaggerItem key={item.step}>
              <article className="flow-card">
                <span className="flow-step">{item.step}</span>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            </StaggerItem>
          ))}
        </StaggerGrid>
      </section>

      <section className="section" id="product">
        <Reveal className="section-heading narrow">
          <p className="eyebrow">See it in action</p>
          <h2>Everything you need. Nothing you don't.</h2>
          <p>
            See exactly how Resume OTG streamlines your application process from start to finish.
          </p>
        </Reveal>
        <div className="product-showcase">
          <div className="video-placeholder">
            <ProductVideo />
          </div>
        </div>
      </section>

      <section className="section" id="support">
        <Reveal className="section-heading narrow">
          <p className="eyebrow">Help and support</p>
          <h2>We're here to help.</h2>
          <p>
            Got a question or need a hand? Reach out anytime. If Resume OTG helped you land that interview, we'd love to hear about it.
          </p>
        </Reveal>
        <SupportActions />
      </section>

      <footer className="site-footer">
        <div>
          <p className="footer-brand">Resume OTG</p>
          <p className="footer-copy">Guided resume optimization for job seekers who want clarity before they click apply.</p>
        </div>
        <nav className="footer-links" aria-label="Footer">
          <a href="/privacy">Privacy</a>
          <a href="#support">Support</a>
          <a href={appUrl} target="_blank" rel="noreferrer">Open app</a>
        </nav>
      </footer>
    </main>
  );
}
