import "./globals.css";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://resume-optimizer-otg.streamlit.app";
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://resume-builder-otg.vercel.app";

export const metadata = {
  title: "Resume OTG — Resume optimization that feels guided, not chaotic.",
  description:
    "Resume OTG helps job seekers build stronger resumes with guided onboarding, profile intelligence, explainable AI optimization, and a Job Tracker that keeps every application organised.",
  metadataBase: new URL(siteUrl),
  openGraph: {
    title: "Resume OTG",
    description:
      "Turn your resume, LinkedIn materials, and job descriptions into a cleaner profile and better-tailored application — with a human workflow you can trust.",
    url: siteUrl,
    siteName: "Resume OTG",
    images: [
      {
        url: "/logo.png",
        width: 966,
        height: 724,
        alt: "Resume OTG — guided resume optimization",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Resume OTG",
    description:
      "Guided resume optimization with explainable AI, profile intelligence, and Job Tracker.",
    images: ["/logo.png"],
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
