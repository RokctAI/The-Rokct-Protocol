# Licensed under the MIT License.
# Copyright 2026 RokctAI

import os
import re
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / '.rokct').exists():
    BASE_DIR = BASE_DIR.parent

EQUITY_SOURCES_DIR = BASE_DIR / "01_equity" / "sources"
EQUITY_SOURCES_DIR.mkdir(parents=True, exist_ok=True)

# --- PRE-SEEDED VC SOURCE DIRECTORIES ---
# High-quality lists and directories of Venture Capitalists and Angel Networks globally
PRE_SEEDED_SOURCES = [
    {
        "name": "Failory Venture Capital Firms in Nigeria",
        "title": "Top VCs in Nigeria",
        "url": "https://www.failory.com/blog/venture-capital-firms-nigeria",
        "slug": "failory_nigeria"
    },
    {
        "name": "Failory Venture Capital Firms in Brazil",
        "title": "Top VCs in Brazil",
        "url": "https://www.failory.com/blog/venture-capital-firms-brazil",
        "slug": "failory_brazil"
    },
    {
        "name": "Failory Venture Capital Firms in Spain",
        "title": "Top VCs in Spain",
        "url": "https://www.failory.com/blog/venture-capital-firms-spain",
        "slug": "failory_spain"
    },
    {
        "name": "Failory Venture Capital Firms in Kenya",
        "title": "Top VCs in Kenya",
        "url": "https://www.failory.com/blog/venture-capital-firms-kenya",
        "slug": "failory_kenya"
    },
    {
        "name": "Signal by NFX Venture Capital Directory",
        "title": "Signal NFX Global VC Directory",
        "url": "https://signal.nfx.com",
        "slug": "signal_nfx_global"
    },
    {
        "name": "Founders Factory Africa Venture Portfolio",
        "title": "Founders Factory Africa Portfolio",
        "url": "https://foundersfactory.africa/",
        "slug": "founders_factory_africa"
    },
    {
        "name": "Latitud Latin America Startup Directory",
        "title": "Latitud LatAm Venture Sources",
        "url": "https://www.latitud.com/",
        "slug": "latitud_latam"
    },
    {
        "name": "Failory Venture Capital Firms in South Korea",
        "title": "Top VCs in South Korea",
        "url": "https://www.failory.com/blog/venture-capital-firms-south-korea",
        "slug": "failory_south_korea"
    },
    {
        "name": "Failory Venture Capital Firms in Mexico",
        "title": "Top VCs in Mexico",
        "url": "https://www.failory.com/blog/venture-capital-firms-mexico",
        "slug": "failory_mexico"
    }
]

def make_slug(name):
    """Generates a clean, system-friendly filename slug."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    return slug.strip('_')

def get_existing_urls_and_filenames():
    """Reads all existing sources to prevent duplicate creation."""
    existing_urls = set()
    existing_filenames = set()
    
    if not EQUITY_SOURCES_DIR.exists():
        return existing_urls, existing_filenames
        
    for file in EQUITY_SOURCES_DIR.glob('*.md'):
        existing_filenames.add(file.name.lower())
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Extract URL from source card
                url_match = re.search(r'-\s+\*\*URL\*\*:\s*(.*)', content, re.I)
                if url_match:
                    existing_urls.add(url_match.group(1).strip().lower())
        except Exception:
            continue
            
    return existing_urls, existing_filenames

def write_source_card(name, title, url, slug=None):
    """Writes a single source card under 01_equity/sources/."""
    existing_urls, existing_filenames = get_existing_urls_and_filenames()
    
    if url.lower() in existing_urls:
        print(f"[Skipped - Duplicate URL] {url}")
        return False
        
    if not slug:
        slug = make_slug(name)
        
    filename = f"{slug}.md"
    if filename.lower() in existing_filenames:
        print(f"[Skipped - Duplicate Filename] {filename}")
        return False
        
    card_path = EQUITY_SOURCES_DIR / filename
    card_content = f"""---
# Source: {title}
- **Name**: {name}
- **Status**: ACTIVE
- **URL**: {url}
---
"""
    with open(card_path, 'w', encoding='utf-8') as f:
        f.write(card_content)
    print(f"[Source Card Created] {filename} -> {url}")
    return True

def search_duckduckgo(query):
    """Searches DuckDuckGo HTML interface for organic VC listing articles."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    url_query = urllib.parse.urlencode({'q': query})
    url = f"https://html.duckduckgo.com/html/?{url_query}"
    
    print(f"Searching: {url}")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        links = []
        # Fallback regex-based parsing of DuckDuckGo HTML results
        pattern = r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>'
        urls = re.findall(pattern, html)
        
        for u in urls:
            u = urllib.parse.unquote(u)
            if 'uddg=' in u:
                u = u.split('uddg=')[1].split('&')[0]
                
            if u.startswith('http') and u not in links:
                # Prioritize high quality venture listing portals
                if any(domain in u.lower() for domain in ['failory.com', 'visible.vc', 'waveup.com', 'openvc.app', 'crunchbase.com']):
                    links.append(u)
        
        return links
    except Exception as e:
        print(f"Web Search Error: {e}")
        return []

def discover_new_sources():
    """Runs a search to discover new VC directory lists."""
    print("Initiating Web Search for new Venture Capital directories...")
    queries = [
        'site:failory.com "venture capital firms"',
        'site:visible.vc "venture capital"',
        'top venture capital firms directory list blog'
    ]
    
    discovered_urls = []
    for q in queries:
        urls = search_duckduckgo(q)
        discovered_urls.extend(urls)
        
    discovered_urls = list(set(discovered_urls))
    print(f"Discovered {len(discovered_urls)} potential venture source lists.")
    
    created_count = 0
    for url in discovered_urls:
        url_lower = url.lower()
        
        # Try to guess a clean name from the URL path
        # Example: https://www.failory.com/blog/venture-capital-firms-colombia
        path_parts = [p for p in url.split('/') if p]
        if not path_parts:
            continue
            
        last_part = path_parts[-1]
        name_clean = last_part.replace('-', ' ').title()
        
        # Parse country/niche name
        match = re.search(r'venture capital firms (.*)', name_clean, re.I)
        if match:
            country = match.group(1).strip()
            name = f"Failory Venture Capital Firms in {country}"
            title = f"Top VCs in {country}"
            slug = f"failory_{make_slug(country)}"
        else:
            name = f"Venture Directory: {name_clean}"
            title = f"Top VC Directory ({name_clean})"
            slug = f"discovered_{make_slug(name_clean)}"
            
        success = write_source_card(name, title, url, slug=slug)
        if success:
            created_count += 1
            
    print(f"Auto-discovery created {created_count} new source cards from web crawling.")

def main():
    print("==================================================")
    print("Equity Venture Source Auto-Discovery")
    print("==================================================")
    
    # 1. Create pre-seeded top tier global source directories
    print("Syncing premium VC/Angel listing sources...")
    pre_seeded_created = 0
    for src in PRE_SEEDED_SOURCES:
        success = write_source_card(src["name"], src["title"], src["url"], slug=src["slug"])
        if success:
            pre_seeded_created += 1
            
    print(f"Pre-seeded {pre_seeded_created} sources successfully.")
    
    # 2. Scrape/Search the web for other country lists
    try:
        discover_new_sources()
    except Exception as e:
        print(f"Scraper execution encountered a minor issue: {e}")
        
    print("\nEquity Source Discovery completed successfully!")

if __name__ == "__main__":
    main()
