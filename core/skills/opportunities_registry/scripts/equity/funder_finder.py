import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path
import sys

# Identify project root
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / '.rokct').exists():
    BASE_DIR = BASE_DIR.parent

# Ensure common imports
sys.path.append(str(BASE_DIR / '.rokct' / 'scripts' / 'equity'))
from funder_manager import FunderManager

def find_candidates(url):
    manager = FunderManager(registry_path=str(BASE_DIR / '01_equity'))
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        candidates = []
        
        # 1. Failory pattern (<h2>1. <a ...>Name</a></h2>)
        if "failory.com" in url:
            for h2 in soup.find_all(['h2', 'h3']):
                text = h2.get_text().strip()
                match = re.search(r'^\d+\.\s+(.*)', text)
                if match:
                    candidates.append(match.group(1).strip())

        # 2. Eqvista table pattern
        elif "eqvista.com" in url:
            table = soup.find('table')
            if table:
                for row in table.find_all('tr')[1:]:
                    cols = row.find_all('td')
                    if len(cols) > 1:
                        name = cols[1].get_text().strip()
                        candidates.append(name)

        # 3. Visible.vc pattern (often in <h3> or <h4>)
        elif "visible.vc" in url:
            for h in soup.find_all(['h2', 'h3', 'h4']):
                text = h.get_text().strip()
                match = re.search(r'^\d+\.\s+(.*)', text)
                if match:
                    candidates.append(match.group(1).strip())
                elif re.match(r'^[A-Z][a-zA-Z\s]+(Investimentos|Capital|Ventures|Partners)$', text):
                    candidates.append(text)

        # 4. BaseTemplates pattern
        elif "basetemplates.com" in url:
            for item in soup.find_all(['h3', 'strong']):
                text = item.get_text().strip()
                if 2 < len(text) < 40 and not any(x in text.lower() for x in ['menu', 'login']):
                    candidates.append(text)

        # 5. Shizune pattern
        elif "shizune.co" in url:
            for item in soup.find_all(['h3', 'strong']):
                text = item.get_text().strip()
                match = re.search(r'^\d+\.\s+(.*)', text)
                if match:
                    candidates.append(match.group(1).strip())
                elif 3 < len(text) < 40 and re.match(r'^[A-Z][a-zA-Z\s0-9]+$', text):
                    candidates.append(text)

        # Generic fallback
        else:
            for h3 in soup.find_all(['h2', 'h3']):
                text = h3.get_text().strip()
                if 3 < len(text) < 50 and not any(x in text.lower() for x in ['menu', 'login', 'search']):
                    candidates.append(text)

        unique_new = []
        for name in list(set(candidates)):
            name = name.split('|')[0].strip() # Clean up pipe suffixes
            if not manager.is_duplicate(name) and len(name) > 2 and len(name) < 60:
                unique_new.append(name)

        return unique_new
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []
