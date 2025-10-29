import os, smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

msg = EmailMessage()
msg["Subject"] = "SCADA SMTP Test"
msg["From"] = os.environ.get("SMTP_FROM")
msg["To"] = os.environ.get("SMTP_FROM")
msg.set_content("If you see this, your SMTP configuration works.")

try:
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as s:
        s.starttls()
        s.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)
    print("✅ SMTP test successful — check your inbox.")
except Exception as e:
    print(f"❌ SMTP test failed: {e}")
