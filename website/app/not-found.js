export default function NotFound() {
  return (
    <main className="content-page">
      <section className="content-panel">
        <p className="eyebrow">Page not found</p>
        <h1>This page is not available.</h1>
        <p>
          The link may have moved, or the page may no longer exist. Head back to Resume OTG to keep going.
        </p>
        <a className="button button-primary" href="/">
          Back to home
        </a>
      </section>
    </main>
  );
}
