import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

def send_registry_emails():
    load_dotenv('.env/production.env')
    
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_user = os.getenv('SMTP_USERNAME')
    smtp_pass = os.getenv('SMTP_PASSWORD')
    
    recipient_file = Path('.rokct/config/registry_recipients.txt')
    published_dir = Path('opportunities/published')
    
    if not recipient_file.exists():
        print("No recipients found. Skipping.")
        return

    # Check for weekly updates
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    updates = {
        'Equity': [f for f in published_dir.glob('01_Equity_*.xlsx') if datetime.fromtimestamp(f.stat().st_mtime) > week_ago],
        'Grants': [f for f in published_dir.glob('02_Grants_*.xlsx') if datetime.fromtimestamp(f.stat().st_mtime) > week_ago],
        'Tenders': [f for f in published_dir.glob('03_Tenders_*.xlsx') if datetime.fromtimestamp(f.stat().st_mtime) > week_ago]
    }

    with open(recipient_file, 'r') as f:
        for line in f:
            if '|' not in line: continue
            email, cats_str = [x.strip() for x in line.split('|')]
            cats = [x.strip() for x in cats_str.split(',')]
            
            attachments = []
            for cat in cats:
                if cat in updates:
                    attachments.extend(updates[cat])
            
            if attachments:
                send_email(email, attachments, smtp_server, smtp_port, smtp_user, smtp_pass)
                print(f"✅ Sent weekly update to {email} ({len(attachments)} files)")

def send_email(to_email, files, server, port, user, password):
    msg = MIMEMultipart()
    msg['From'] = f"RokctAI Registry <{user}>"
    msg['To'] = to_email
    msg['Subject'] = f"📂 Weekly Registry Update: {datetime.now().strftime('%Y-%m-%d')}"
    
    body = "Hi,\n\nPlease find the latest filtered opportunity reports attached based on your subscriptions.\n\nBest,\nRokctAI Agent"
    msg.attach(MIMEText(body, 'plain'))
    
    for f_path in files:
        with open(f_path, "rb") as fil:
            part = MIMEApplication(fil.read(), Name=f_path.name)
            part['Content-Disposition'] = f'attachment; filename="{f_path.name}"'
            msg.attach(part)
            
    use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
            
    with smtplib.SMTP(server, port) as server:
        if use_tls:
            server.starttls()
        server.login(user, password)
        server.send_message(msg)

if __name__ == "__main__":
    send_registry_emails()
