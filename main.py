import datetime
import os
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

# --- KONFIGURACE ZE ZABEZPEČENÝCH PROMĚNNÝCH GITHUB ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))

TARGET_URL = "https://www.nsoud.cz/uredni-deska/obcanskopravni-a-obchodni-kolegium/vyhlasovana-rozhodnuti"


def ziskej_rozhodnuti_za_posledni_dny(dny=7):
    """Stáhne hlavní stránku úřední desky a vyhledá odkaz na nová rozhodnutí."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    response = requests.get(TARGET_URL, headers=headers)
    if response.status_code != 200:
        print(f"Chyba při načítání stránky: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    odkazy = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "rozhodnuti" in href or "Judikatura" in href:
            full_url = href if href.startswith("http") else f"https://www.nsoud.cz{href}"
            if full_url not in odkazy:
                odkazy.append(full_url)

    # Zpracujeme až 10 nejnovějších rozhodnutí za týden
    return odkazy[:10]


def stahni_text_rozhodnuti(url):
    """Stáhne text samotného rozhodnutí."""
    try:
        res = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    " AppleWebKit/537.36"
                )
            },
            timeout=15,
        )
        soup = BeautifulSoup(res.text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.extract()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)[:15000]
    except Exception as e:
        print(f"Chyba při stahování {url}: {e}")
        return None


def sumarizuj_gemini(text_rozhodnuti):
    """Zpracuje text pomocí Gemini API přesně podle požadovaného formátu."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
    Jsi špičkový právní analytik. Analyzuj následující rozhodnutí Nejvyššího soudu ČR 
    a připrav z něj výstup v přesně stanoveném formátu pro e-mailový přehled.

    POŽADOVANÝ FORMÁT KAŽDÉHO SHRUNUTÍ:
    ### [Nadpis vystihující hlavní témata a podstatu rozhodnutí]
    * **Spisová značka:** [Doplň spisovou značku]
    * **Dotčená oblast:** [Např. Obchodní právo / Náhrada škody / Smlouvy]
    
    **Stručné shrnutí nosných závěrů:**
    [Napiš 3 až 5 výstižných bodů nebo odstavců vysvětlujících klíčové právní závěry Nejvyššího soudu a praktický dopad rozhodnutí.]

    Text rozhodnutí k analýze:
    {text_rozhodnuti}
    """

    response = model.generate_content(prompt)
    return response.text


def posli_email(obsah_html):
    """Odešle výsledný e-mail."""
    msg = MIMEMultipart("alternative")
    dnes = datetime.date.today().strftime("%d.%m.%Y")
    msg["Subject"] = Header(
        f"Přehled rozhodnutí Nejvyššího soudu – {dnes}", "utf-8"
    )
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    html_text = obsah_html.replace("\n", "<br>").replace("### ", "<h2>").replace("</h2><br>", "</h2>")
    
    body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h1 style="color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 8px;">
            Nová rozhodnutí Nejvyššího soudu ČR (7 dní)
        </h1>
        <p><i>Automatický přehled vyhlášených rozhodnutí za poslední týden.</i></p>
        <hr>
        {html_text}
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
        print("Chybí konfigurace API klíčů nebo e-mailu!")
        return

    print("Stahuji seznam nově vyhlášených rozhodnutí za 7 dní...")
    odkazy = ziskej_rozhodnuti_za_posledni_dny(7)

    if not odkazy:
        print("Nenalezena žádná nová rozhodnutí.")
        return

    vysledna_shrnuti = []
    for idx, url in enumerate(odkazy, 1):
        print(f"Zpracovávám rozhodnutí {idx}/{len(odkazy)}: {url}")
        text = stahni_text_rozhodnuti(url)
        if text:
            shrnuti = sumarizuj_gemini(text)
            vysledna_shrnuti.append(
                f"{shrnuti}\n\n**Odkaz na plné znění:** [{url}]({url})\n<hr>"
            )

    if vysledna_shrnuti:
        kompletni_obsah = "\n\n".join(vysledna_shrnuti)
        print("Odesílám e-mail...")
        posli_email(kompletni_obsah)
        print("Hotovo, e-mail odeslán!")


ALL_CONFIGURED = all(
    [GEMINI_API_KEY, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]
)

if __name__ == "__main__":
    main()
