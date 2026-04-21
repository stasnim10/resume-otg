"use client";

import { useState } from "react";

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://resume-optimizer-otg.streamlit.app";
const contactEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "tasnimsimum@gmail.com";
const donateUrl = "https://buy.stripe.com/cNiaEZ4KwgLJdtA2C0dMI01";

const shareMessage =
  `I’ve been using Resume OTG to build and optimize applications with a calmer workflow. ` +
  `You can try it here: ${appUrl}`;

export function SupportActions() {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(shareMessage);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="support-simple">
      <div className="support-button-row">
        <a
          className="button button-secondary"
          href={`mailto:${contactEmail}?subject=${encodeURIComponent("Need help with Resume OTG")}`}
        >
          Need Help?
        </a>
        <a className="button button-support" href={donateUrl} target="_blank" rel="noreferrer">
          Support the Developer
        </a>
      </div>

      <div className="share-card">
        <p className="share-card-title">Share with a friend</p>
        <p className="share-card-copy">
          Copy one ready-made message with the app link and share it anywhere you want.
        </p>
        <div className="share-message-box">{shareMessage}</div>
        <button className="copy-link-button" type="button" onClick={handleCopy}>
          {copied ? "Copied" : "Copy share message"}
        </button>
      </div>
    </div>
  );
}
