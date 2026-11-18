# Salama

> Know they arrived. Pay as you can.

Salama is a school attendance and fee-payment platform for parents, schools and gate staff, built for the **Africa's Talking WIT Kampala EdTech Hackathon (21 November 2026)**. It works over SMS and USSD, so parents need no smartphone and no internet.

*Salama is a working name and may change.*

---

## The Problem

Children drop out of school quietly. By the time a school or a parent notices, it is often too late. Three problems feed this:

1. **Parents lack visibility.** They don't know whether their child reached school, or how regularly they attend.
2. **Fee payment is all-or-nothing.** Many families struggle to pay a full term's fees at once, so small affordable instalments are not an option for them.
3. **Schools see the warning signs late.** Missed days and unpaid balances are usually tracked separately (a paper register here, a ledger there), so nobody connects them until the child has stopped coming.

## The Solution

Salama links attendance and fees in one system, with three users:

| User | Device | What they do |
|------|--------|--------------|
| **Gate keeper (askari)** | Any smartphone browser | Scans each student's ID card QR code. The screen shows green (checked in) or red (unrecognised card). |
| **School (headteacher, bursar, teachers)** | Laptop or phone browser | Watches a live dashboard: who has arrived, who is absent, who has paid. |
| **Parent** | Any phone, including basic feature phones | Gets an SMS when their child arrives. Dials a USSD code to check attendance, see the fee balance and pay an instalment. |

### How it works

```
Student ID card (QR code)
        |
        v
Askari scans it (web page on a phone)
        |
        v
   Salama server  --->  Database (students, parents, attendance, payments)
     |        |
     |        +--->  School dashboard updates live
     |
     +--->  Africa's Talking SMS  --->  Parent's phone: "Sarah arrived at 7:42 AM"

Parent dials USSD code
        |
        v
Africa's Talking  --->  Salama server  --->  Menu: attendance / fee balance / pay
```

The devices never talk to each other directly. Each one connects only to the Salama server, and the server does the connecting.

### What makes it different

Most attendance tools only send alerts. Salama joins attendance with fee payments, so a school can see which students are **both missing days and falling behind on fees**. That is the early-warning pattern that precedes dropping out. The first version flags these students with a simple, transparent rule (for example: absent 3 or more days in the last 2 weeks and an unpaid balance), so staff can follow up with the family early.

## Features

- [ ] QR code check-in via a browser-based scanner (no app install)
- [ ] Automatic SMS to the parent when their child arrives
- [ ] Live school dashboard (present / absent, arrival times)
- [ ] USSD menu for parents: attendance history, fee balance, pay an instalment
- [ ] Mobile money fee instalments (sandbox / simulated in the demo)
- [ ] Rule-based dropout-risk flag on the dashboard
- [ ] SMS reminder at the cut-off time to parents of students who have not arrived

## Africa's Talking APIs Used

- **SMS**: arrival alerts, absence alerts and payment receipts
- **USSD**: the parent's on-demand menu
- **Payments**: fee instalments (sandbox)

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite for the hackathon demo
- **Frontend:** plain HTML, CSS and JavaScript (scanner page and dashboard)
- **Messaging:** Africa's Talking Python SDK
- **Hosting:** Render, or ngrok for local testing

## Getting Started

### Prerequisites

- Python 3.10 or newer
- Git
- A free [Africa's Talking](https://africastalking.com) account, using the **Sandbox** app
- (For testing) [ngrok](https://ngrok.com), so Africa's Talking can reach your local server

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/salama-school-alerts.git
cd salama-school-alerts
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install flask africastalking python-dotenv
```

### 3. Add your Africa's Talking credentials

Create a file named `.env` in the project root:

```
AT_USERNAME=sandbox
AT_API_KEY=your_sandbox_api_key_here
```

**Never commit this file.** Make sure `.gitignore` contains:

```
.env
venv/
__pycache__/
*.db
```

### 4. Run the server

```bash
python app.py
```

The app runs at `http://localhost:5000`.

### 5. Expose the server so Africa's Talking can reach it

```bash
ngrok http 5000
```

Copy the `https://...` address ngrok prints. You will use it in the next step.

### 6. Connect USSD in the Africa's Talking sandbox

1. In the sandbox dashboard, create a USSD service code.
2. Set the callback URL to `https://<your-ngrok-address>/ussd`.
3. Open the **Simulator** in the dashboard, enter a parent's phone number and dial the code.

### 7. Try the demo

1. Open the scanner page on a phone: `https://<your-ngrok-address>/scan` (HTTPS is needed for camera access).
2. Open the dashboard on a laptop: `https://<your-ngrok-address>/dashboard`.
3. Show a student's QR code on another screen and scan it.
4. Watch the dashboard update and the parent's SMS arrive.

## Planned Project Structure

```
salama-school-alerts/
├── app.py              # Flask server and routes
├── database.py         # Database setup and queries
├── sms.py              # Africa's Talking SMS helper
├── ussd.py             # USSD menu logic
├── templates/
│   ├── scan.html       # Askari QR scanner page
│   └── dashboard.html  # School dashboard
├── static/             # CSS and JavaScript
├── .env                # Secrets (not committed)
├── .gitignore
└── README.md
```

## Demo Notes

- USSD runs through the Africa's Talking simulator, and fee payments are sandbox/test payments. No real money moves.
- Demo data uses fictional students and a teammate's phone number as the "parent".
- A manual "enter student ID" box is available on the scanner page as a backup if the camera fails.

## Roadmap

- Voice alerts in local languages for parents who cannot read SMS
- Bulk student upload from a CSV or Excel file
- Exam results shared with parents through USSD
- Smarter dropout-risk scoring using attendance and payment trends
- Multi-school support and a per-term subscription model

## Team

- _Name 1_: role
- _Name 2_: role
- _Name 3_: role
- _Name 4_: role

## License

To be decided by the team (MIT is a common choice for hackathon projects).
