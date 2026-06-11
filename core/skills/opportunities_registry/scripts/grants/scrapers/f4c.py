# Licensed under the MIT License.
# Copyright 2024 RokctAI

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import sys
import re
import time
import logging

# Identify project root
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / '.rokct').exists():
    BASE_DIR = BASE_DIR.parent

# Setup Logging
LOG_DIR = BASE_DIR / '.rokct' / 'agent' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

scraper_logger = logging.getLogger('f4c_scraper')
scraper_logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_DIR / 'f4c_scraper.log')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
scraper_logger.addHandler(fh)

failure_logger = logging.getLogger('f4c_failures')
failure_logger.setLevel(logging.ERROR)
ffh = logging.FileHandler(LOG_DIR / 'f4c_failures.log')
ffh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
failure_logger.addHandler(ffh)

def normalize_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ('%B %d, %Y', '%B %d %Y', '%d %B %Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None

def get_existing_urls():
    urls = set()
    grants_dir = BASE_DIR / '02_grants'
    if not grants_dir.exists():
        return urls
    for f in grants_dir.glob('*.md'):
        if f.name == 'template.md' or f.name == 'registry_audit_log.md':
            continue
        try:
            content = f.read_text(encoding='utf-8')
            match = re.search(r'\*\*Source\*\*:\s*(https?://[^\s\n\)]+)', content)
            if match:
                urls.add(match.group(1).strip())
        except:
            continue
    return urls

def get_active_source():
    sources_dir = BASE_DIR / '02_grants' / 'sources'
    for f in sources_dir.glob('*.md'):
        if 'fundsforcompanies' in f.name.lower():
            content = f.read_text(encoding='utf-8')
            status_match = re.search(r'Status\*\*:\s*(ACTIVE)', content, re.I)
            url_match = re.search(r'URL\*\*:\s*(https?://[^\s\n]+)', content)
            if status_match and url_match:
                return url_match.group(1).strip(), f.name
    return None, None

def run():
    base_url, source_card = get_active_source()
    if not base_url:
        scraper_logger.error("No ACTIVE Funds for Companies source found.")
        return

    api_url = f"{base_url.rstrip('/')}/wp-json/wp/v2/posts"
    existing_urls = get_existing_urls()
    scraper_logger.info(f"Loaded {len(existing_urls)} existing URLs for deduplication.")

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})

    new_opportunities = []
    page = 1
    today = datetime.now().strftime('%Y-%m-%d')

    scraper_logger.info(f"Starting WP API scrape of {api_url}")

    while len(new_opportunities) < 100:
        params = {
            'per_page': 100,
            'page': page,
            '_fields': 'id,title,link,date,content,tags,area,grant-size,grant-duration,class_list'
        }
        try:
            resp = session.get(api_url, params=params, timeout=30)
            if resp.status_code != 200:
                scraper_logger.warning(f"API returned {resp.status_code} for page {page}. Stopping.")
                break

            posts = resp.json()
            if not posts: break

            total_pages = int(resp.headers.get('X-WP-TotalPages', 1))

            for post in posts:
                if len(new_opportunities) >= 100: break

                source_url = post['link']
                if source_url in existing_urls: continue

                title = post['title']['rendered']
                raw_content = post['content']['rendered']
                soup = BeautifulSoup(raw_content, 'lxml')
                text_content = soup.get_text(" ", strip=True)

                # Deadline
                deadline_match = re.search(r'Deadline Date:\s*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', text_content)
                deadline = normalize_date(deadline_match.group(1)) if deadline_match else None
                if deadline and deadline < today: continue

                # Funding - FIXED: escaped $ sign
                funding = "Unspecified"
                funding_patterns = [
                    r'(?:grant funding from|funding from|funding available for this topic is|grants of|up to|maximum of|investment of up to|budget of|allocated|prizes range from|award is|contribution is|prize of|receive funding of|funding of up to|funding of|receive a grant of|funding support of up to)\s*(?:€|\$|£|EUR|USD|CAD|AUD|PLN|SEK|NOK|DKK)\s?[\d,.]+\s?(?:million|billion|m|b)?\s?(?:to|-)?\s?(?:€|\$|£|EUR|USD|CAD|AUD|PLN|SEK|NOK|DKK)?\s?[\d,.]+\s?(?:million|billion|m|b)?',
                    r'(?:€|\$|£|EUR|USD|CAD|AUD|PLN|SEK|NOK|DKK)\s?[\d,.]+\s?(?:million|billion|m|b)?',
                    r'[\d,.]+\s?(?:million|billion|m|b)?\s?(?:€|\$|£|EUR|USD|CAD|AUD|PLN|SEK|NOK|DKK)'
                ]
                for pattern in funding_patterns:
                    match = re.search(pattern, text_content, re.I)
                    if match:
                        funding = match.group(0).strip()
                        funding = re.sub(r'[.\s]+$', '', funding)
                        break

                # Applying Link
                applying_link = source_url
                applying_org_candidate = "Unspecified"
                blacklist = ['fundsforngos', 'statcounter', 'cookiedatabase', 'facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 'quora', 'google', 'apple', 'eepurl.com', 'wordpress.org', 'cookieconsent', 'managed-consent', 'mailchimp']

                # Check .OP_content specifically
                op_content = soup.find(class_="OP_content")
                if op_content:
                    all_op_links = op_content.find_all('a', href=True)
                    valid_op_links = [l for l in all_op_links if not any(b in l['href'].lower() for b in blacklist)]
                    if valid_op_links:
                        # Official link is usually the last one in .OP_content
                        applying_link = valid_op_links[-1]['href']
                        applying_org_candidate = valid_op_links[-1].get_text().strip()

                # Fallback vicinity search near info markers
                if applying_link == source_url:
                    official_marker = soup.find(string=re.compile(r'For more information|visit|official website|Apply Here', re.I))
                    if official_marker:
                        parent = official_marker.parent
                        links = parent.find_all('a', href=True) or parent.parent.find_all('a', href=True)
                        for l in links:
                            if not any(b in l['href'].lower() for b in blacklist):
                                applying_link = l['href']
                                applying_org_candidate = l.get_text().strip()
                                break

                # Organization detection
                org = "Unspecified"
                known_orgs = ["European Commission", "Innovate UK", "United Nations", "UNDP", "World Bank", "Global Environment Facility", "African Development Bank", "Asian Development Bank", "UNESCO", "USAID", "UK Research and Innovation", "Foundations", "National Geographic", "Google", "Microsoft", "Monttu Ventures", "Łódź Special Economic Zone", "Portuguese Foundation for Science and Technology", "FCT", "Lundbeck Foundation", "Barclays Eagle Labs", "MG Motor", "Nasscom", "HKEX", "EIT Food", "EIT Manufacturing", "European Space Agency", "ESA", "Department for Energy Security and Net Zero", "Innovate UK", "Horizon Europe", "Startup Spark"]
                for known in known_orgs:
                    if known.lower() in text_content.lower():
                        org = known
                        break

                if org == "Unspecified":
                    # Look for specific phrases anywhere
                    # "X leads this initiative", "X manages the call", "X announced by"
                    lead_match = re.search(r'([^.]{5,100}?)\s+(?:leads this initiative|leads the initiative|manages the program|administers|announced the|launched the|has launched)', text_content, re.I)
                    if lead_match:
                        cand = lead_match.group(1).strip()
                        if not any(kw in cand.lower() for kw in ['this', 'programme', 'program', 'initiative', 'call']):
                            org = cand

                if org == "Unspecified" or org == "FCT":
                    if applying_org_candidate != "Unspecified" and len(applying_org_candidate) > 2 and len(applying_org_candidate) < 100:
                        if not any(kw in applying_org_candidate.lower() for kw in ['click here', 'apply', 'website', 'link', 'portal', 'page', 'here', 'visit', 'read more', 'GOV.UK']):
                            # Favor existing full name over abbreviation
                            if org == "FCT" and "Portuguese Foundation" in applying_org_candidate:
                                org = applying_org_candidate
                            elif org == "Unspecified":
                                org = applying_org_candidate

                if org == "Unspecified":
                    # Try sentence parsing
                    cleaned_text = re.sub(r'Deadline Date:\s*[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}', '', text_content).strip()
                    cleaned_text = re.sub(r'^(The|In collaboration with|Under the|Through the)\s+', '', cleaned_text, flags=re.I)
                    # Broad look for subjects preceding actions
                    org_match = re.search(r'^([^.]{5,150}?)\s+(?:is|has|invites|announces|seeking|accepting|launched|announced|leads|offers|provides)', cleaned_text)
                    if org_match:
                        cand = org_match.group(1).strip()
                        cand = re.split(r'\s+(is|has|invites|leads|offers|provides)\s+', cand, flags=re.I)[0].strip()
                        if len(cand) > 100: cand = cand.split(',')[0].strip()
                        # If cand looks like a grant name, don't use it yet if we have other options
                        if not any(kw in cand.lower() for kw in ['call for', 'apply now', 'grant opportunity', 'opportunity to']):
                            org = cand

                if org == "Unspecified" and ":" in title:
                    potential = title.split(":")[0].strip()
                    potential = re.sub(r'^(Open Call|Apply Now|Applications open|CFPs|RFAs|CFAs|RFPs|Nominations open|Entries Open)\s*:?\s*', '', potential, flags=re.I).strip()
                    if len(potential) > 3 and len(potential) < 60: org = potential

                # Eligibility
                countries = [c.replace('tag-', '').replace('-', ' ').title() for c in post.get('class_list', []) if c.startswith('tag-')]
                country_str = ", ".join(countries)
                eligibility = f"Eligible Countries: {country_str}. " if country_str else ""
                elig_patterns = [r'Any legal entity[^.]+\.', r'Eligibility\s*[:\s]\s*([^.]+)', r'Eligible applicants include\s*([^.]+)', r'Open to\s*([^.]+)', r'Applications are invited from\s*([^.]+)']
                for pattern in elig_patterns:
                    match = re.search(pattern, text_content, re.I)
                    if match:
                        eligibility += match.group(0).strip()
                        break
                if not eligibility: eligibility = "See source for details."

                safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
                date_prefix = deadline if deadline else "Ongoing"
                filename = f"{date_prefix}_{safe_title}.md"
                if len(filename) > 100: filename = filename[:97] + ".md"

                card_content = f"""# Grant Opportunity: {title}

## Quick Stats
- **Organization**: {org}
- **Deadline**: {deadline if deadline else 'Ongoing'}
- **Funding Amount**: {funding}
- **Focus Area**: General

## Eligibility
- {eligibility}

## Description
{title} - Refer to source for full description.

## How to Apply
- **Applying Link**: {applying_link}
- **Source**: {source_url}
- **Source Card**: sources/{source_card}

## Audit & Status
- **Verification Status**: UNVERIFIED
- **Last Verified**: {today}
"""
                filepath = BASE_DIR / '02_grants' / filename
                filepath.write_text(card_content, encoding='utf-8')
                scraper_logger.info(f"Created card: {filename}")
                new_opportunities.append(source_url)
                if org == "Unspecified" or funding == "Unspecified":
                    scraper_logger.warning(f"Card {filename} has unspecified fields (Org: {org}, Funding: {funding}).")

            if page >= total_pages: break
            page += 1
        except Exception as e:
            failure_logger.error(f"Error on API page {page}: {e}")
            break
    scraper_logger.info(f"Scrape completed. Created {len(new_opportunities)} new cards.")

if __name__ == "__main__":
    run()
