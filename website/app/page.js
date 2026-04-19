import Image from "next/image";
import { StickyNav } from "./components/StickyNav";
import { SupportActions } from "@/components/SupportActions";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://resume-optimizer-otg.streamlit.app";

const steps = [
  {
    step: "01",
    title: "Start with onboarding",
    body: "Add your basics, career stage, and target direction in a guided flow built for first-time users.",
  },
  {
    step: "02",
    title: "Upload your materials",
    body: "Bring in your resume, LinkedIn export, or supporting documents so the app can build your profile faster.",
  },
  {
    step: "03",
    title: "Review before continuing",
    body: "Check what the app extracted and correct anything that looks wrong before your profile is saved.",
  },
  {
    step: "04",
    title: "Optimize with confidence",
    body: "Match your resume to a role, review the suggested changes, and export only when you are happy with the result.",
  },
];

const productNotes = [
  "Guided onboarding linked directly to profile creation",
  "Review-first resume optimization instead of blind rewriting",
  "Job Tracker that keeps each role and application context together",
];

export default function HomePage() {
  return (
    <main className="page-shell">
      <StickyNav>
        <header className="site-header">
          <a className="brand-mark" href="#top">
            <div className="brand-lockup">
              <Image src="/logo.jpeg" alt="Resume Builder OTG logo" width={44} height={44} />
              <div>
                <p className="brand-name">Resume Builder OTG</p>
                <p className="brand-subtitle">Resume optimization that feels guided, not chaotic.</p>
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
          <p className="eyebrow">Resume Builder OTG</p>
          <h1>Build stronger applications with a calmer workflow.</h1>
          <p className="hero-simple-body">
            Resume Builder OTG helps users move from onboarding to profile creation to resume
            optimization without feeling lost, overloaded, or forced to trust hidden AI output.
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
            src="/hero-image.png"
            alt="Resume Builder OTG hero artwork"
            width={1478}
            height={831}
            className="hero-image"
            priority
          />
        </div>
      </section>

      <section className="section" id="how-it-works">
        <div className="section-heading narrow">
          <p className="eyebrow">How it works</p>
          <h2>Simple, guided, and review-first.</h2>
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
          <h2>The product experience, kept simple.</h2>
          <p>
            This section will hold a short walkthrough video of the app once publishing is ready. For
            now, the focus stays on the actual product and the flow users will experience inside it.
          </p>
        </div>
        <div className="product-showcase">
          <div className="video-placeholder">
            <span>Product walkthrough video will be added here</span>
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
          <h2>Keep support easy to reach.</h2>
          <p>
            Users should always have a simple help path, plus a way to support the project or share it
            with someone else if it was useful.
          </p>
        </div>
        <SupportActions />
      </section>
    </main>
  );
}
