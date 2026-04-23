import Image from "next/image";
import { StickyNav } from "./components/StickyNav";
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

const productNotes = [
  "Guided setup that instantly builds your professional profile.",
  "Transparent AI suggestions—you review every change before it's applied.",
  "Integrated Job Tracker to organize your applications in one clean view.",
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
          <h1>Craft your Perfect Resume. Land the Interview.</h1>
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
        </div>

        <div className="hero-simple-visual">
          <Image
            src="/hero-image.jpeg"
            alt="Resume OTG hero artwork"
            width={2290}
            height={1856}
            className="hero-image"
            priority
          />
        </div>
      </section>

      <section className="section" id="how-it-works">
        <div className="section-heading narrow">
          <p className="eyebrow">How it works</p>
          <h2>Simple, Guided, and Review-first.</h2>
        </div>
        <div className="flow-grid">
          {steps.map((item) => (
            <article className="flow-card" key={item.step}>
              <span className="flow-step">{item.step}</span>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section" id="product">
        <div className="section-heading narrow">
          <p className="eyebrow">Product</p>
          <h2>Everything you Need. Nothing you Don't.</h2>
          <p>
            See exactly how Resume OTG streamlines your application process from start to finish.
          </p>
        </div>
        <div className="product-showcase">
          <div className="video-placeholder">
            <span>Product walkthrough coming soon</span>
          </div>
          <div className="product-note-list">
            {productNotes.map((note) => (
              <div className="product-note" key={note}>
                {note}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="support">
        <div className="section-heading narrow">
          <p className="eyebrow">Help and support</p>
          <h2>We're here to Help.</h2>
          <p>
            Got a question or need a hand? Reach out anytime. If Resume OTG helped you land that interview, we'd love to hear about it.
          </p>
        </div>
        <SupportActions />
      </section>
    </main>
  );
}
