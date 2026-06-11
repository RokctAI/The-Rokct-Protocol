import sys
import re
import requests
from pathlib import Path

# Fields to extract URLs from
URL_FIELDS = [
    r"-\s+\*\*Website\*\*:\s*(?P<url>https?://[^\s]+)",
    r"-\s+\*\*Source / Verification\*\*:\s*(?P<url>https?://[^\s]+)",
    r"-\s+\*\*Applying Link\*\*:\s*(?P<url>https?://[^\s]+)"
]

def verify_url(url):
    """Checks if a URL is reachable, skipping LinkedIn."""
    if "linkedin.com" in url.lower():
        return True, "Skipped (LinkedIn)"

    try:
        # Use a browser-like User-Agent to avoid some basic bot blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.head(url, timeout=10, headers=headers, allow_redirects=True)
        # If HEAD fails, try GET as some servers block HEAD
        if response.status_code >= 400:
            response = requests.get(url, timeout=10, headers=headers, stream=True)

        if response.status_code < 400:
            return True, f"Status: {response.status_code}"
        else:
            return False, f"Status: {response.status_code}"
    except Exception as e:
        return False, str(e)

def main():
    files = sys.argv[1:]
    if not files:
        print("No files provided for verification.")
        sys.exit(0)

    failed_urls = []

    for filepath in files:
        path = Path(filepath)
        if not path.exists():
            continue

        print(f"Checking {path.name}...")
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

            for field_regex in URL_FIELDS:
                match = re.search(field_regex, content, re.I)
                if match:
                    url = match.group('url').strip()
                    success, message = verify_url(url)
                    if not success:
                        failed_urls.append((path.name, url, message))
                        print(f"  ❌ {url} -> {message}")
                    else:
                        print(f"  ✅ {url}")

    if failed_urls:
        print("\n--- Failed URL Verification ---")
        for file, url, error in failed_urls:
            print(f"File: {file}\n  URL: {url}\n  Error: {error}\n")
        sys.exit(1)
    else:
        print("\nAll URLs verified successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()
