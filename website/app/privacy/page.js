export const metadata = {
  title: "Privacy — Resume OTG",
  description: "How Resume OTG handles resume, profile, and application data.",
};

export default function PrivacyPage() {
  return (
    <main className="content-page">
      <a className="back-link" href="/">Resume OTG</a>
      <section className="content-panel">
        <p className="eyebrow">Privacy</p>
        <h1>Resume and career data should be handled carefully.</h1>
        <p>
          Resume OTG is designed for job seekers who may be working with sensitive career information.
          Only add information you are comfortable using inside the app and connected services.
        </p>
        <h2>What you may provide</h2>
        <p>
          You may upload or enter resume text, LinkedIn-style profile details, career history, job
          descriptions, and application notes so the app can help organize and tailor your materials.
        </p>
        <h2>How the app uses it</h2>
        <p>
          The app uses your inputs to structure your career profile, compare it with job descriptions,
          and generate resume-improvement guidance. Do not include passwords, government IDs, financial
          account details, or other unnecessary sensitive data.
        </p>
        <h2>Questions</h2>
        <p>
          Use the support form on the homepage for privacy questions, deletion requests, or data-handling
          concerns.
        </p>
      </section>
    </main>
  );
}
