import Image from "next/image";
import { Reveal } from "./components/Reveal";
import { StaggerGrid, StaggerItem } from "./components/StaggerGrid";
import { StickyNav } from "./components/StickyNav";
import { AnimatedHero } from "@/components/ui/animated-hero";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://resume-optimizer-otg.streamlit.app";
const contactEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "tasnimsimum@gmail.com";
const linkedinUrl =
  process.env.NEXT_PUBLIC_LINKEDIN_URL || "https://www.linkedin.com/in/simum-tasnim/";
const donateUrl = "https://buy.stripe.com/cNiaEZ4KwgLJdtA2C0dMI01";
const shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(
  "I've been using Resume Builder OTG to turn resumes and job descriptions into cleaner, more tailored applications. " +
    appUrl
)}`;

const heroPoints = [
  "Guided onboarding that builds your profile from your existing materials",
  "Review-first optimization so you approve changes before export",
  "Job Tracker that keeps each role, version, and follow-up in one place",
];

const flow = [
  {
    step: "01",
    title: "Tell us who you are",
    body: "A short conversational onboarding captures your name, career stage, target roles, and preferences without overwhelming you on day one.",
  },
  {
    step: "02",
    title: "Upload your existing materials",
    body: "Resume, LinkedIn PDF, or other documents auto-build your profile so the hard setup work happens once, not every time you apply.",
  },
  {
    step: "03",
    title: "Cross-check and confirm",
    body: "The app shows exactly what it extracted and asks you to review each section before anything becomes part of your profile.",
  },
  {
    step: "04",
    title: "Optimize with confidence",
    body: "Bring in a job description, generate tailored improvements, review the changes, then save the role to Job Tracker.",
  },
];

const productSections = [
  {
    kicker: "Onboarding",
    title: "A smoother first five minutes.",
    body: "New users should never feel like they are doing admin work for the app. Resume Builder OTG uses onboarding to collect just enough context, then lets uploaded materials do the heavy lifting.",
    bullets: [
      "Conversational first-run experience",
      "Automatic profile building from resume and LinkedIn materials",
      "Section-by-section profile confirmation before continuing",
    ],
  },
  {
    kicker: "Optimization",
    title: "A review flow you can trust.",
    body: "Instead of black-box rewriting, the app shows before-and-after fit, explains the changes, and keeps the user in control all the way to export.",
    bullets: [
      "Readable fit improvement story",
      "Structured change review before download",
      "Support for standard mode and private mode paths",
    ],
  },
  {
    kicker: "Job Tracker",
    title: "More than a pile of old runs.",
    body: "Every saved role can become a living application record with the job description, status, notes, and the exact resume version you used.",
    bullets: [
      "Status tracking from preparing to offer",
      "Save application materials when you want to",
      "Keep context for interview callbacks and follow-ups",
    ],
  },
];

const faqs = [
  {
    q: "Do I need technical knowledge to use it?",
    a: "No. The product is built around guided onboarding, editable review steps, and plain-language prompts so first-time users can move through it without understanding models, prompts, or endpoints.",
  },
  {
    q: "Will private mode work on the public version?",
    a: "Private mode depends on a local Ollama setup and is best experienced on a supported local install. Standard mode works on the public hosted version with your own API key.",
  },
  {
    q: "What if the app extracts something incorrectly?",
    a: "That is exactly why the confirmation step matters. The app shows what it found and lets you correct each section before it becomes part of your profile.",
  },
];

export default function HomePage() {
  return (
    <main className="page-shell">

      {/* ── Sticky nav ──────────────────────────────────────────────────── */}
      <StickyNav>
        <header className="site-header">
          <a className="brand-mark" href="#top">
            <div className="brand-lockup">
              <Image src="/logo.png" alt="Resume Builder OTG logo" width={46} height={46} />
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

      {/* ── Animated Hero ────────────────────────────────────────────── */}
      <div id="top" style={{ width: "min(100%, var(--max-width))", margin: "0 auto" }}>
        <AnimatedHero />
      </div>

      {/* ── How it works ────────────────────────────────────────────────── */}
      <section className="section section-flow" id="how-it-works">
        <Reveal>
          <div className="section-heading">
            <p className="eyebrow">How it works</p>
            <h2>A product flow built around confidence.</h2>
            <p>
              Help users move from first visit to tailored application without feeling lost,
              overloaded, or forced to trust opaque AI output.
            </p>
          </div>
        </Reveal>
        <StaggerGrid className="flow-grid">
          {flow.map((item) => (
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

      {/* ── Product pillars ─────────────────────────────────────────────── */}
      <section className="section section-product" id="product">
        <Reveal>
          <div className="section-heading narrow">
            <p className="eyebrow">Product pillars</p>
            <h2>Built for the actual pain points of applying, not just AI demos.</h2>
          </div>
        </Reveal>
        <div className="feature-stack">
          {productSections.map((section, i) => (
            <Reveal key={section.title} delay={i * 0.06}>
              <article className="feature-row">
                <div className="feature-copy">
                  <p className="feature-kicker">{section.kicker}</p>
                  <h3>{section.title}</h3>
                  <p>{section.body}</p>
                </div>
                <ul className="feature-list">
                  {section.bullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── Proof card ──────────────────────────────────────────────────── */}
      <Reveal className="section">
        <div className="proof-card">
          <div>
            <p className="eyebrow">Designed for launch readiness</p>
            <h2>A calmer path into public testing.</h2>
          </div>
          <StaggerGrid className="proof-grid">
            {[
              {
                title: "Trust first",
                body: "Review before export, confirm before profile save, and help when users get stuck.",
              },
              {
                title: "Fewer repeated steps",
                body: "Profile intelligence and Job Tracker make every future application lighter.",
              },
              {
                title: "Human support still matters",
                body: "Users always have a help path before they abandon the product.",
              },
            ].map((item) => (
              <StaggerItem key={item.title}>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.body}</p>
                </div>
              </StaggerItem>
            ))}
          </StaggerGrid>
        </div>
      </Reveal>

      {/* ── Screenshots ─────────────────────────────────────────────────── */}
      <section className="section section-screenshots" id="screenshots">
        <Reveal>
          <div className="section-heading">
            <p className="eyebrow">Inside the app</p>
            <h2>See the workflow in action.</h2>
            <p>
              From first-run onboarding to the final optimized export — every step is designed to
              keep you in control.
            </p>
          </div>
        </Reveal>
        {/* Replace placeholder divs with <Image> once you have real screenshots */}
        <StaggerGrid className="screenshots-grid">
          <StaggerItem>
            <figure className="screenshot-item screenshot-large">
              <div className="screenshot-placeholder">
                <span>Onboarding — welcome &amp; profile setup</span>
              </div>
              <figcaption>Guided onboarding that builds your profile automatically</figcaption>
            </figure>
          </StaggerItem>
          <StaggerItem>
            <figure className="screenshot-item">
              <div className="screenshot-placeholder">
                <span>Optimization — before &amp; after score</span>
              </div>
              <figcaption>Explainable before/after fit score</figcaption>
            </figure>
          </StaggerItem>
          <StaggerItem>
            <figure className="screenshot-item">
              <div className="screenshot-placeholder">
                <span>Job Tracker — application history</span>
              </div>
              <figcaption>Job Tracker keeps every application organised</figcaption>
            </figure>
          </StaggerItem>
        </StaggerGrid>
      </section>

      {/* ── FAQ & support ───────────────────────────────────────────────── */}
      <section className="section section-faq" id="support">
        <Reveal>
          <div className="section-heading narrow">
            <p className="eyebrow">Help and support</p>
            <h2>Users should never be left alone with a confusing screen.</h2>
            <p>
              A strong launch includes guided help inside the product and a clear path to reach a
              real person when needed.
            </p>
          </div>
        </Reveal>
        <div className="faq-grid">
          <StaggerGrid className="faq-list">
            {faqs.map((item) => (
              <StaggerItem key={item.q}>
                <article className="faq-item">
                  <h3>{item.q}</h3>
                  <p>{item.a}</p>
                </article>
              </StaggerItem>
            ))}
          </StaggerGrid>
          <Reveal delay={0.1}>
            <aside className="support-card">
              <p className="support-kicker">Need help?</p>
              <h3>In-product guidance first, direct support when needed.</h3>
              <p>
                The app includes task-based help for onboarding, profile review, optimization, and
                Job Tracker. If that still isn&apos;t enough, reach out directly.
              </p>
              <div className="support-links" style={{ marginTop: "20px" }}>
                <a className="button button-primary" href={`mailto:${contactEmail}`}>
                  Email support
                </a>
                <a
                  className="button button-secondary"
                  href={linkedinUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Connect on LinkedIn
                </a>
              </div>
            </aside>
          </Reveal>
        </div>
      </section>

      {/* ── Support the developer ────────────────────────────────────────── */}
      <Reveal className="section section-support-dev">
        <div className="support-dev-card">
          <div className="support-dev-copy">
            <p className="eyebrow">Built by one person, for real job seekers</p>
            <h2>If this saved you time, a coffee goes a long way.</h2>
            <p>
              Resume Builder OTG is a solo side project. Every donation helps keep the app free,
              fund future features, and cover API costs for users who need it most.
            </p>
            <div className="support-dev-actions">
              <a className="button button-support" href={donateUrl} target="_blank" rel="noreferrer">
                ☕ Buy me a coffee
              </a>
              <a
                className="button button-secondary"
                href={shareUrl}
                target="_blank"
                rel="noreferrer"
              >
                Share with a friend
              </a>
            </div>
          </div>
          <aside className="support-dev-aside">
            {[
              { title: "Free to use", body: "No account required to start optimizing" },
              { title: "Private mode available", body: "Run AI locally — no data leaves your machine" },
              { title: "Actively maintained", body: "Built and improved based on real user feedback" },
            ].map((stat) => (
              <div className="support-dev-stat" key={stat.title}>
                <strong>{stat.title}</strong>
                <p>{stat.body}</p>
              </div>
            ))}
          </aside>
        </div>
      </Reveal>

      {/* ── Final CTA ───────────────────────────────────────────────────── */}
      <Reveal className="section section-cta">
        <div className="cta-card">
          <div>
            <p className="eyebrow">Ready to try it?</p>
            <h2>Open the app and experience the workflow directly.</h2>
          </div>
          <div className="cta-actions">
            <a className="button button-primary" href={appUrl} target="_blank" rel="noreferrer">
              Launch app — it&apos;s free
            </a>
            <a className="button button-secondary" href={`mailto:${contactEmail}`}>
              Send feedback
            </a>
          </div>
        </div>
      </Reveal>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <footer className="site-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <p className="brand-name">Resume Builder OTG</p>
            <p className="footer-tagline">Resume optimization that feels guided, not chaotic.</p>
            <div className="footer-social">
              <a href={`mailto:${contactEmail}`}>Email</a>
              <a href={linkedinUrl} target="_blank" rel="noreferrer">LinkedIn</a>
              <a href={donateUrl} target="_blank" rel="noreferrer">☕ Support</a>
            </div>
          </div>
          <nav className="footer-nav" aria-label="Footer navigation">
            <div className="footer-nav-group">
              <p className="footer-nav-label">Product</p>
              <a href="#how-it-works">How it works</a>
              <a href="#product">Features</a>
              <a href="#screenshots">Screenshots</a>
              <a href={appUrl} target="_blank" rel="noreferrer">Open app</a>
            </div>
            <div className="footer-nav-group">
              <p className="footer-nav-label">Support</p>
              <a href="#support">Help &amp; FAQ</a>
              <a href={`mailto:${contactEmail}`}>Email us</a>
              <a href={linkedinUrl} target="_blank" rel="noreferrer">LinkedIn</a>
            </div>
            <div className="footer-nav-group">
              <p className="footer-nav-label">Support the project</p>
              <a href={donateUrl} target="_blank" rel="noreferrer">Buy me a coffee</a>
            </div>
          </nav>
        </div>
        <div className="footer-bottom">
          <p>© {new Date().getFullYear()} Resume Builder OTG. Built with care by one developer.</p>
        </div>
      </footer>
    </main>
  );
}
