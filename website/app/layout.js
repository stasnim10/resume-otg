import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://www.resumeotg.app";
const ogImage = "/hero-image.png";

export const metadata = {
  title: "Resume OTG — Resume optimization that feels guided, not chaotic.",
  description:
    "Resume OTG helps job seekers build stronger resumes with guided onboarding, profile intelligence, explainable AI optimization, and a Job Tracker that keeps every application organised.",
  metadataBase: new URL(siteUrl),
  manifest: "/site.webmanifest",
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-96x96.png", sizes: "96x96", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "Resume OTG",
    description:
      "Turn your resume, LinkedIn materials, and job descriptions into a cleaner profile and better-tailored application — with a human workflow you can trust.",
    url: siteUrl,
    siteName: "Resume OTG",
    images: [
      {
        url: ogImage,
        width: 1060,
        height: 834,
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
    images: [ogImage],
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
