import "./globals.css";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://resume-optimizer-otg.streamlit.app";

export const metadata = {
  title: "Resume Builder OTG — Resume optimization that feels guided, not chaotic.",
  description:
    "Resume Builder OTG helps job seekers build stronger resumes with guided onboarding, profile intelligence, explainable AI optimization, and a Job Tracker that keeps every application organised.",
  metadataBase: new URL("https://resumebuilderotg.com"),
  openGraph: {
    title: "Resume Builder OTG",
    description:
      "Turn your resume, LinkedIn materials, and job descriptions into a cleaner profile and better-tailored application — with a human workflow you can trust.",
    url: appUrl,
    siteName: "Resume Builder OTG",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Resume Builder OTG — guided resume optimization",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Resume Builder OTG",
    description:
      "Guided resume optimization with explainable AI, profile intelligence, and Job Tracker.",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
