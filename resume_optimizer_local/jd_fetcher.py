"""
Helpers for extracting job descriptions from pasted job-post URLs.
"""
from __future__ import annotations

import json
import re
from html import unescape
from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def looks_like_url(value: str) -> bool:
    """Return True when the input resembles a web URL."""
    value = value.strip()
    return value.startswith("http://") or value.startswith("https://")


def _clean_text(text: str) -> str:
    """Normalize extracted text into readable paragraphs."""
    text = unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    cleaned_lines = [line for line in lines if line]
    return "\n".join(cleaned_lines)


def _extract_from_json_ld(soup: BeautifulSoup) -> Optional[str]:
    """Try extracting a JobPosting description from JSON-LD."""
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            description = item.get("description")
            title = item.get("title") or item.get("name")
            if item_type == "JobPosting" and description:
                parts = [title] if title else []
                parts.append(BeautifulSoup(description, "html.parser").get_text("\n"))
                return _clean_text("\n".join(parts))
    return None


def extract_role_from_meta(html: str) -> Optional[str]:
    """Extract the job title from page metadata when available."""
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        ("meta", {"property": "og:title"}, "content"),
        ("meta", {"name": "title"}, "content"),
        ("meta", {"property": "twitter:title"}, "content"),
    ]
    for tag_name, attrs, field in selectors:
        node = soup.find(tag_name, attrs=attrs)
        if not node:
            continue
        raw_title = (node.get(field) or "").strip()
        if not raw_title:
            continue
        title = raw_title
        for splitter in [" | ", " at ", " - LinkedIn", " | LinkedIn"]:
            if splitter in title:
                title = title.split(splitter)[0].strip()
        title = re.sub(r"\s+-\s+Remote$", "", title, flags=re.IGNORECASE).strip()
        if title:
            return title
    return None


def _extract_main_text(soup: BeautifulSoup) -> str:
    """Extract readable text from common job-post content containers."""
    selectors = [
        "main",
        "article",
        "[role='main']",
        ".job-description",
        ".jobDescriptionContent",
        ".description",
        ".posting-requirements",
        ".content",
        "#content",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = _clean_text(node.get_text("\n"))
            if len(text) > 300:
                return text

    body = soup.body or soup
    return _clean_text(body.get_text("\n"))


def _extract_linkedin_jd_from_html(soup: BeautifulSoup) -> Optional[str]:
    """Extract only the main LinkedIn job content block when available."""
    title = extract_role_from_meta(str(soup)) or ""

    company = ""
    location = ""
    company_selectors = [
        ".job-details-jobs-unified-top-card__company-name",
        ".topcard__org-name-link",
        ".jobs-unified-top-card__company-name",
    ]
    location_selectors = [
        ".job-details-jobs-unified-top-card__tertiary-description-container",
        ".topcard__flavor--bullet",
        ".jobs-unified-top-card__subtitle-primary-grouping",
    ]

    for selector in company_selectors:
        node = soup.select_one(selector)
        if node:
            company = _clean_text(node.get_text(" ", strip=True))
            break

    for selector in location_selectors:
        node = soup.select_one(selector)
        if node:
            location = _clean_text(node.get_text(" ", strip=True))
            break

    content_selectors = [
        ".show-more-less-html__markup",
        ".jobs-description__container .jobs-box__html-content",
        ".jobs-description-content__text",
        ".jobs-description",
    ]
    body_text = ""
    for selector in content_selectors:
        node = soup.select_one(selector)
        if node:
            body_text = _clean_text(node.get_text("\n"))
            if len(body_text) > 250:
                break

    if not body_text:
        return None

    lines = []
    if title:
        lines.append(title)
    if company:
        lines.append(company)
    if location and location.lower() != company.lower():
        lines.append(location)
    lines.append(body_text)
    return _clean_text("\n".join(lines))


def extract_job_description_from_html(html: str) -> str:
    """Extract the best-effort JD text from raw HTML."""
    soup = BeautifulSoup(html, "html.parser")

    json_ld_text = _extract_from_json_ld(soup)
    if json_ld_text:
        return json_ld_text

    linkedin_text = _extract_linkedin_jd_from_html(soup)
    if linkedin_text:
        return linkedin_text

    text = _extract_main_text(soup)
    if len(text) < 120:
        raise ValueError("We could not find enough readable job description text on that page.")
    return text


def fetch_job_description_from_url(url: str, timeout: int = 15) -> Tuple[str, str, Optional[str]]:
    """
    Fetch a job-post page and return extracted JD text plus the final URL.

    Raises ValueError with friendly messages for UI display.
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise ValueError(
            "We could not load that job post URL automatically. "
            "Please paste the job description text manually."
        ) from error

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise ValueError(
            "That link did not return a standard web page we can extract from. "
            "Please paste the job description text manually."
        )

    try:
        extracted = extract_job_description_from_html(response.text)
    except Exception as error:
        raise ValueError(
            "We loaded the page but could not confidently extract the job description. "
            "Please paste the job description text manually."
        ) from error

    role_hint = extract_role_from_meta(response.text)
    return extracted, response.url, role_hint
