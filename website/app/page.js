import Image from "next/image";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://resume-optimizer-otg.streamlit.app";
const contactEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "tasnimsimum@gmail.com";
const linkedinUrl =
  process.env.NEXT_PUBLIC_LINKEDIN_URL || "https://www.linkedin.com/in/simum-tasnim/";
const donateUrl = "https://buy.stripe.com/cNiaEZ4KwgLJdtA2C0dMI01";

const highlights = [
  {
    title: "Guided onboarding that actually builds your profile",
    body:
      "Start with a few simple questions, upload your resume or LinkedIn material, and let the app draft your profile automatically before asking you to confirm every important detail.",
  },
  {
    title: "Review-first optimization, not blind AI rewriting",
    body:
      "Every optimization is surfaced as changes you can inspect before you export. The app is designed to earn trust, not ask for it.",
  },
  {
    title: "A profile that gets smarter over time",
    body:
      "Your profile, saved job targets, materials, and feedback loops become the foundation for faster future applications instead of making you start from zero each time.",
  },
];

const flow = [
  {
    step: "01",
    title: "Tell us who you are",
    body:
      "A short, conversational onboarding captures your name, career stage, target roles, and preferences without overwhelming you on day one.",
  },
  {
    step: "02",
    title: "Upload your existing materials",
    body:
      "Resume, LinkedIn PDF, or other documents are used to auto-build your profile so the hard setup work happens once, not every time you apply.",
  },
  {
    step: "03",
    title: "Cross-check and confirm",
    body:
      "The app shows exactly what it extracted and asks you to review each section before anything becomes part of your profile.",
  },
  {
    step: "04",
    title: "Optimize with confidence",
    body:
      "Bring in a job description, generate tailored improvements, review the suggested changes, then save the role into Job Tracker if you want to keep the full application story.",
  },
];

const productSections = [
  {
    kicker: "Onboarding",
    title: "A smoother first five minutes.",
    body:
      "New users should never feel like they are doing admin work for the app. Resume Builder OTG uses onboarding to collect just enough context, then lets uploaded materials do the heavy lifting.",
    bullets: [
      "Conversational first-run experience",
      "Automatic profile building from resume and LinkedIn materials",
      "Section-by-section profile confirmation before continuing",
    ],
  },
  {
    kicker: "Optimization",
    title: "A review flow you can trust.",
    body:
      "Instead of black-box rewriting, the app shows before and after fit, explains the changes, and keeps the user in control all the way to export.",
    bullets: [
      "Readable fit improvement story",
      "Structured change review before download",
      "Support for standard mode and private mode paths",
    ],
  },
  {
    kicker: "Job Tracker",
    title: "More than a pile of old runs.",
    body:
      "Every saved role can become a living application record with the job description, status, notes, and the exact resume version you used when it matters.",
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
    a:
      "No. The product is being designed around guided onboarding, editable review steps, and plain-language prompts so first-time users can move through it without understanding models, prompts, or endpoints.",
  },
  {
    q: "Will private mode work on the public website?",
    a:
      "The public website is meant to introduce the product and send users into the app. Private mode depends on a local Ollama setup, so it is best experienced on a supported local install.",
  },
  {
    q: "What if the app extracts something incorrectly?",
    a:
      "That is exactly why the confirmation step matters. The app should show users what it found and let them correct profile sections before continuing.",
  },
];

export default function HomePage() {
  return (
    <main className="page-shell">
      <div className="backdrop backdrop-one" />
      <div className="backdrop backdrop-two" />

      <header className="site-header">
        <a className="brand-mark" href="#top">
          <div className="brand-lockup">
            <Image src="/logo.png" alt="Resume Builder OTG logo" width={52} height={52} />
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

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">Resume Builder OTG</p>
          <h1>Build stronger applications without losing trust in the process.</h1>
          <p className="hero-body">
            Resume Builder OTG helps job seekers turn resumes, LinkedIn materials, and job descriptions
            into cleaner profiles, better tailored drafts, and application-ready documents with a calmer,
            more human workflow.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href={appUrl} target="_blank" rel="noreferrer">
              Start optimizing
            </a>
            <a className="button button-secondary" href="#how-it-works">
              See the workflow
            </a>
          </div>
          <div className="hero-trust">
            <span>Guided onboarding</span>
            <span>Editable profile confirmation</span>
            <span>Explainable resume review</span>
          </div>
        </div>

        <div className="hero-panel">
          <div className="panel-card panel-primary">
            <p className="panel-kicker">What makes it different</p>
            <h2>The app should understand the user before it asks them to optimize anything.</h2>
            <p>
              Onboarding, profile creation, job targeting, review, and application tracking should feel
              like one connected journey, not a collection of disconnected tools.
            </p>
          </div>
          <div className="panel-grid">
            {highlights.map((item) => (
              <article className="panel-card panel-secondary" key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section-flow" id="how-it-works">
        <div className="section-heading">
          <p className="eyebrow">How it works</p>
          <h2>A product flow built around confidence.</h2>
          <p>
            The goal is simple: help users move from first visit to tailored application without feeling
            lost, overloaded, or forced to trust opaque AI output.
          </p>
        </div>
        <div className="flow-grid">
          {flow.map((item) => (
            <article className="flow-card" key={item.step}>
              <span className="flow-step">{item.step}</span>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section section-product" id="product">
        <div className="section-heading narrow">
          <p className="eyebrow">Product pillars</p>
          <h2>Built for the actual pain points of applying, not just AI demos.</h2>
        </div>
        <div className="feature-stack">
          {productSections.map((section) => (
            <article className="feature-row" key={section.title}>
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
          ))}
        </div>
      </section>

      <section className="section section-proof">
        <div className="proof-card">
          <div>
            <p className="eyebrow">Designed for launch readiness</p>
            <h2>A calmer path into public testing.</h2>
          </div>
          <div className="proof-grid">
            <div>
              <strong>Trust first</strong>
              <p>Review before export, confirm before profile save, and help when users get stuck.</p>
            </div>
            <div>
              <strong>Fewer repeated steps</strong>
              <p>Profile intelligence and Job Tracker make every future application lighter.</p>
            </div>
            <div>
              <strong>Human support still matters</strong>
              <p>Users should always have a help path before they abandon the product.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="section section-faq" id="support">
        <div className="section-heading narrow">
          <p className="eyebrow">Help and support</p>
          <h2>Users should never be left alone with a confusing screen.</h2>
          <p>
            A strong launch includes guided help inside the product and a clear path to reach a real
            person when needed.
          </p>
        </div>

        <div className="faq-grid">
          <div className="faq-list">
            {faqs.map((item) => (
              <article className="faq-item" key={item.q}>
                <h3>{item.q}</h3>
                <p>{item.a}</p>
              </article>
            ))}
          </div>

          <aside className="support-card">
            <p className="support-kicker">Need help?</p>
            <h3>Guide users in-product first, then offer direct support.</h3>
            <p>
              The product should include task-based help for onboarding, profile review, optimization, and
              saving to Job Tracker. If that still is not enough, users should be able to contact you
              directly.
            </p>
            <div className="support-links">
              <a className="button button-primary" href={`mailto:${contactEmail}`}>
                Email support
              </a>
              <a className="button button-secondary" href={linkedinUrl} target="_blank" rel="noreferrer">
                Connect on LinkedIn
              </a>
            </div>
          </aside>
        </div>
      </section>

      {/* ── Screenshots ──────────────────────────────────────────────────── */}
      <section className="section section-screenshots" id="screenshots">
        <div className="section-heading">
          <p className="eyebrow">Inside the app</p>
          <h2>See the workflow in action.</h2>
          <p>
            From first-run onboarding to the final optimized export — every step is designed to keep
            you in control.
          </p>
        </div>
        {/* Drop real screenshots into /public/screenshots/ and replace the src values below */}
        <div className="screenshots-grid">
          <figure className="screenshot-item screenshot-large">
            <div className="screenshot-placeholder">
              <span>Onboarding — welcome &amp; profile setup</span>
            </div>
            <figcaption>Guided onboarding that builds your profile automatically</figcaption>
          </figure>
          <figure className="screenshot-item">
            <div className="screenshot-placeholder">
              <span>Optimization — before &amp; after score</span>
            </div>
            <figcaption>Explainable before/after fit score</figcaption>
          </figure>
          <figure className="screenshot-item">
            <div className="screenshot-placeholder">
              <span>Job Tracker — application history</span>
            </div>
            <figcaption>Job Tracker keeps every application organised</figcaption>
          </figure>
        </div>
      </section>

      {/* ── Support the developer ─────────────────────────────────────────── */}
      <section className="section section-support-dev">
        <div className="support-dev-card">
          <div className="support-dev-copy">
            <p className="eyebrow">Built by one person, for real job seekers</p>
            <h2>If this saved you time, a coffee goes a long way.</h2>
            <p>
              Resume Builder OTG is a solo side project. Every donation helps keep the app free,
              fund future features, and cover API costs for users who need it most.
            </p>
            <div className="support-dev-actions">
              <a className="button button-coffee" href={donateUrl} target="_blank" rel="noreferrer">
                ☕ Buy me a coffee
              </a>
              <a
                className="button button-secondary"
                href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(
                  "Just used Resume Builder OTG to optimise my resume for a job application. Free, guided, and surprisingly good. " + appUrl
                )}`}
                target="_blank"
                rel="noreferrer"
              >
                Share on Twitter / X
              </a>
            </div>
          </div>
          <aside className="support-dev-aside">
            <div className="support-dev-stat">
              <strong>Free to use</strong>
              <p>No account required to start optimizing</p>
            </div>
            <div className="support-dev-stat">
              <strong>Private mode available</strong>
              <p>Run AI locally — no data leaves your machine</p>
            </div>
            <div className="support-dev-stat">
              <strong>Actively maintained</strong>
              <p>Built and improved based on real user feedback</p>
            </div>
          </aside>
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────────── */}
      <section className="section section-cta">
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
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer className="site-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <p className="brand-name">Resume Builder OTG</p>
            <p className="footer-tagline">Resume optimization that feels guided, not chaotic.</p>
            <div className="footer-social">
              <a href={`mailto:${contactEmail}`} aria-label="Email support">
                Email
              </a>
              <a href={linkedinUrl} target="_blank" rel="noreferrer" aria-label="LinkedIn">
                LinkedIn
              </a>
              <a href={donateUrl} target="_blank" rel="noreferrer">
                ☕ Support
              </a>
            </div>
          </div>
          <nav className="footer-nav" aria-label="Footer navigation">
            <div className="footer-nav-group">
              <p className="footer-nav-label">Product</p>
              <a href="#how-it-works">How it works</a>
              <a href="#product">Features</a>
              <a href="#screenshots">Screenshots</a>
              <a href={appUrl} target="_blank" rel="noreferrer">
                Open app
              </a>
            </div>
            <div className="footer-nav-group">
              <p className="footer-nav-label">Support</p>
              <a href="#support">Help &amp; FAQ</a>
              <a href={`mailto:${contactEmail}`}>Email us</a>
              <a href={linkedinUrl} target="_blank" rel="noreferrer">
                LinkedIn
              </a>
            </div>
            <div className="footer-nav-group">
              <p className="footer-nav-label">Support the project</p>
              <a href={donateUrl} target="_blank" rel="noreferrer">
                Buy me a coffee
              </a>
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
