import datetime
import os
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# --- KONFIGURACE ZE ZABEZPEČENÝCH PROMĚNNÝCH GITHUB ---
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))

TARGET_URL = "https://www.nsoud.cz/uredni-deska/obcanskopravni-a-obchodni-kolegium/vyhlasovana-rozhodnuti"


def ziskej_rozhodnuti():
    """Stáhne hlavní stránku úřední desky a vytáhne seznam rozhodnutí a odkazů."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    try:
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Chyba při načítání stránky: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        polozky = []

        # Hledáme odkazy na nová rozhodnutí na úřední desce
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text(strip=True)

            if ("rozhodnuti" in href or "Judikatura" in href) and len(text) > 3:
                full_url = (
                    href
                    if href.startswith("http")
                    else f"https://www.nsoud.cz{href}"
                )

                # Zamezení duplicitám
                if not any(p["url"] == full_url for p in polozky):
                    polozky.append({"nazev": text, "url": full_url})

        return polozky[:15]
    except Exception as e:
        print(f"Chyba při stahování: {e}")
        return []


def posli_email(polozky):
    """Odešle přehledný HTML e-mail se seznamem rozhodnutí."""
    msg = MIMEMultipart("alternative")
    dnes = datetime.date.today().strftime("%d.%m.%Y")
    msg["Subject"] = Header(
        f"Přehled rozhodnutí Nejvyššího soudu – {dnes}", "utf-8"
    )
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    # Sestavení řádků seznamu
    seznam_html = ""
    for idx, item in enumerate(polozky, 1):
        seznam_html += f"""
        <li style="margin-bottom: 12px;">
            <strong style="font-size: 15px;">{item['nazev']}</strong><br>
            <a href="{item['url']}" style="color: #1a56db; text-decoration: underline;">Otevřít plné znění na NSoud.cz</a>
        </li>
        """

    body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 8px;">
            Vyhlášená rozhodnutí Nejvyššího soudu ČR
        </h2>
        <p>Automatický přehled nově vyhlášených rozhodnutí k dnešnímu dni ({dnes}):</p>
        <ol style="padding-left: 20px;">
            {seznam_html}
        </ol>
        <hr style="border: none; border-top: 1px solid #ccc; margin-top: 20px;">
        <p style="font-size: 12px; color: #666;">Odesláno automaticky ze skriptu GitHub Actions.</p>
      </body>
    </html>
    """

    msg.attach(MIMEText(body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())


def main():
    if not ALL_CONFIGURED:
        print("Chybí konfigurace e-mailových údajů v GitHub Secrets!")
        return

    print("Stahuji seznam nově vyhlášených rozhodnutí...")
    polozky = ziskej_rozhodnuti()

    if not polozky:
        print("Nenalezena žádná rozhodnutí.")
        return

    print(f"Nalezeno {len(polozky)} rozhodnutí. Odesílám e-mail...")
    posli_email(polozky)
    print("Hotovo, e-mail byl úspěšně odeslán!")


ALL_CONFIGURED = all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER])

if __name__ == "__main__":
    main()
