# LinkedIn Opdrachten Alert — Setup

## Wat doet dit?

Zoekt 2x per dag (08:00 en 17:00) op LinkedIn naar posts over branding- en webdesign-opdrachten in Nederland + België en stuurt je een HTML-e-mail met de nieuwste berichten.

---

## 1. Installeer dependencies

```bash
pip install -r requirements.txt
```

---

## 2. Configureer je `.env`

Kopieer het voorbeeld en vul je gegevens in:

```bash
cp .env.example .env
nano .env
```

### LinkedIn-inloggegevens
Gebruik je normale LinkedIn e-mail en wachtwoord. De scraper logt in via de officieuze LinkedIn API.

> **Tip:** Gebruik bij voorkeur een apart LinkedIn-account om je hoofdaccount te beschermen.

### Gmail App Password (voor e-mail)
Gmail staat standaard geen directe wachtwoordinlog toe. Maak een **App Password** aan:
1. Ga naar [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Kies *Andere (aangepaste naam)* → geef het een naam → Genereren
3. Kopieer het 16-cijferige wachtwoord naar `SMTP_PASSWORD`

---

## 3. Test direct

```bash
python main.py --run-now
```

Je ziet logs in je terminal en ontvangt een test-e-mail.

---

## 4. Draaien als achtergrondproces (Linux/Mac)

### Optie A: Simpel in de achtergrond

```bash
nohup python main.py > linkedin_alerts.log 2>&1 &
```

### Optie B: systemd service (aanbevolen op Linux)

Maak het bestand `/etc/systemd/system/linkedin-alerts.service` aan:

```ini
[Unit]
Description=LinkedIn Opdrachten Alert
After=network.target

[Service]
Type=simple
WorkingDirectory=/pad/naar/Linkedin-Scraper
ExecStart=/usr/bin/python3 /pad/naar/Linkedin-Scraper/main.py
Restart=on-failure
RestartSec=60
EnvironmentFile=/pad/naar/Linkedin-Scraper/.env

[Install]
WantedBy=multi-user.target
```

Activeer en start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable linkedin-alerts
sudo systemctl start linkedin-alerts
sudo systemctl status linkedin-alerts
```

### Optie C: Draaien op een VPS/server
Zet de code op een goedkope VPS (€3-5/maand) zodat hij 24/7 draait. Gebruik dan optie B.

---

## 5. Zoekwoorden aanpassen

Pas de lijst `SEARCH_QUERIES` in `scraper.py` aan naar je eigen niche:

```python
SEARCH_QUERIES = [
    "freelance designer gezocht",
    "branding opdracht freelance",
    # voeg toe wat relevant is voor jou
]
```

---

## Veelgestelde vragen

**Kan LinkedIn mijn account blokkeren?**  
De scraper pauzeert automatisch tussen queries. Gebruik bij voorkeur een apart account of wees voorzichtig met je hoofdaccount.

**Hoe verander ik de tijden?**  
Pas `SCHEDULE_TIMES` aan in je `.env`, bijv. `SCHEDULE_TIMES=07:30,16:00`.

**Hoe zorg ik dat ik geen dubbele posts krijg?**  
Dat regelt `tracker.py` automatisch via een lokale SQLite-database (`seen_posts.db`).
