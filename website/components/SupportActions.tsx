"use client";

import { useState } from "react";

const supportFormUrl =
  "https://docs.google.com/forms/d/e/1FAIpQLSf6mVr-SiJGt25xf-IqyigH1tP7gLDUqKALsL0s7LkVuf-vhw/viewform?usp=sharing";
const donateUrl =
  process.env.NEXT_PUBLIC_DONATE_URL || "https://buy.stripe.com/cNiaEZ4KwgLJdtA2C0dMI01";
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://www.resumeotg.app";

const shareMessage =
  "I’ve been using Resume OTG to build and optimize my applications. " +
  `You can try it here: ${siteUrl.replace(/^https?:\/\//, "")}`;

export function SupportActions() {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);

  async function handleCopy() {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareMessage);
      } else {
        const el = document.createElement("textarea");
        el.value = shareMessage;
        el.setAttribute("readonly", "");
        el.style.position = "fixed";
        el.style.top = "-1000px";
        document.body.appendChild(el);
        el.select();
        document.execCommand("copy");
        document.body.removeChild(el);
      }
      setCopied(true);
      setFailed(false);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
      setFailed(true);
      window.setTimeout(() => setFailed(false), 2200);
    }
  }

  return (
    <div className="support-simple">
      <div className="support-button-row">
        <a className="button button-secondary" href={supportFormUrl} target="_blank" rel="noreferrer">
          Need Help?
        </a>
        <a className="button button-support" href={donateUrl} target="_blank" rel="noreferrer">
          Keep Resume OTG free
        </a>
      </div>

      <div className="share-card">
        <p className="share-card-title">Share with a friend</p>
        <p className="share-card-copy">
          Copy one ready-made message with the app link and share it anywhere you want.
        </p>
        <div className="share-message-box">{shareMessage}</div>
        <button
          className={`copy-link-button${copied ? " is-copied" : ""}${failed ? " is-failed" : ""}`}
          type="button"
          onClick={handleCopy}
        >
          {copied ? "✓ Copied" : failed ? "Copy failed" : "Copy share message"}
        </button>
      </div>
    </div>
  );
}
