import os
from datetime import datetime
from flask import (
    Flask,
    Response,
    render_template_string,
    request,
    jsonify,
    session,
    redirect,
    url_for,
)
from dotenv import load_dotenv
import africastalking

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "salama-hackathon-secret-key")

USERNAME = os.getenv("AT_USERNAME", "sandbox")
API_KEY = os.getenv("AT_API_KEY")
ADMIN_NUMBER = os.getenv("ADMIN_NUMBER", "2026")

africastalking.initialize(USERNAME, API_KEY)
sms = africastalking.SMS

STUDENTS_DB = {
    "STU-001": {
        "name": "Namukasa Sarah",
        "class": "P.6",
        "parent_phone": "+256700000001",
        "preferred_lang": "en",
        "fee_status": "Cleared",
        "fee_balance": 0,
    },
    "STU-002": {
        "name": "Muwonge Daniel",
        "class": "P.4",
        "parent_phone": "+256700000002",
        "preferred_lang": "lg",
        "fee_status": "Balance Due",
        "fee_balance": 120000,
    },
    "STU-003": {
        "name": "Natukunda Faith",
        "class": "P.5",
        "parent_phone": "+256700000003",
        "preferred_lang": "nyn",
        "fee_status": "Balance Due",
        "fee_balance": 85000,
    },
    "STU-004": {
        "name": "Okello Brian",
        "class": "P.7",
        "parent_phone": "+256700000004",
        "preferred_lang": "ach",
        "fee_status": "Cleared",
        "fee_balance": 0,
    },
    "STU-005": {
        "name": "Byaruhanga Grace",
        "class": "P.3",
        "parent_phone": "+256700000005",
        "preferred_lang": "nyn",
        "fee_status": "Balance Due",
        "fee_balance": 45000,
    },
}

LANG_LABELS = {
    "en": "English",
    "lg": "Luganda",
    "nyn": "Runyankole",
    "ach": "Acholi",
}

LANG_SHORT = {
    "en": "EN",
    "lg": "LG",
    "nyn": "NYN",
    "ach": "ACH",
}

# Stores check-in entries in memory for the live session
CHECKINS = []

# Maps (YYYY-MM-DD, student_id) -> check-in time string so each student only checks in once per day
DAILY_CHECKED_IN = {}

# Maps (YYYY-MM-DD, student_id) -> {"time": str, "lang_label": str} when parent reports child sick/excused via USSD
DAILY_EXCUSED = {}

# Stores parent callback requests made via USSD
CALLBACK_REQUESTS = []

# Stores absentee roll-call sweep SMS alerts
ABSENTEE_ALERTS = []

# Toggleable daily fee reminder context for parent check-in SMS
DASHBOARD_SETTINGS = {
    "daily_fee_reminder": False,
}

SCANNER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Salama Gate Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; background: #f4f7f6; margin: 0; }
        .card { background: white; padding: 24px 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); max-width: 450px; margin: auto; }
        input { width: 80%; padding: 12px; font-size: 18px; margin: 10px 0; border: 1px solid #ccc; border-radius: 6px; }
        button { background: #2e7d32; color: white; border: none; padding: 12px 25px; font-size: 18px; border-radius: 6px; cursor: pointer; }
        .result { margin-top: 20px; padding: 15px; border-radius: 6px; font-weight: bold; cursor: pointer; transition: opacity 0.3s ease; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
        .warning { background: #fff3cd; color: #856404; }
        #reader { width: 100%; max-width: 350px; margin: auto; display: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Salama Gate Check-In</h2>
        <p>Scan student ID QR code or type ID:</p>

        <button onclick="startScanner()" id="scan-btn" style="background: #1976d2; margin-bottom: 15px;">📷 Open Camera Scanner</button>
        <div id="reader"></div>

        <form method="POST" action="/scan" id="checkin-form">
            <input type="text" id="student_id" name="student_id" placeholder="e.g. STU-001" autocomplete="off" autofocus required><br>
            <button type="submit">Verify & Notify</button>
        </form>

        {% if message %}
            <div id="result-banner" class="result {{ status }}" onclick="clearScannerState()">{{ message }}</div>
        {% endif %}
    </div>

    <script>
        let html5QrCode = null;
        let isSubmitting = false;

        function clearScannerState() {
            const inputEl = document.getElementById('student_id');
            if (inputEl) {
                inputEl.value = '';
                inputEl.focus();
            }
            const banner = document.getElementById('result-banner');
            if (banner) {
                banner.style.display = 'none';
                banner.textContent = '';
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            const inputEl = document.getElementById('student_id');
            if (inputEl) {
                inputEl.value = '';
                inputEl.focus();
            }

            const banner = document.getElementById('result-banner');
            if (banner) {
                setTimeout(() => {
                    clearScannerState();
                }, 4000);
            }
        });

        function startScanner() {
            isSubmitting = false;
            document.getElementById('reader').style.display = 'block';
            document.getElementById('scan-btn').style.display = 'none';

            html5QrCode = new Html5Qrcode("reader");

            function onScanSuccess(decodedText, decodedResult) {
                if (isSubmitting) return;
                isSubmitting = true;

                const cleanCode = (decodedText || '').trim();
                const inputEl = document.getElementById('student_id');
                inputEl.value = cleanCode;

                const stopPromise = html5QrCode ? html5QrCode.stop().catch(() => {}) : Promise.resolve();
                stopPromise.finally(() => {
                    document.getElementById('reader').style.display = 'none';
                    document.getElementById('scan-btn').style.display = 'inline-block';
                    document.getElementById('checkin-form').submit();
                });
            }

            html5QrCode.start(
                { facingMode: "environment" },
                { fps: 10, qrbox: { width: 250, height: 250 } },
                onScanSuccess
            ).catch(err => {
                alert("Camera access denied or unavailable. Use manual typing.");
                document.getElementById('reader').style.display = 'none';
                document.getElementById('scan-btn').style.display = 'inline-block';
            });
        }
    </script>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Salama Admin Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; background: #f4f7f6; margin: 0; padding: 16px; }
        .card { background: white; padding: 28px 24px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 380px; width: 100%; text-align: center; }
        input[type="number"], input[type="password"] { width: 100%; box-sizing: border-box; padding: 12px; font-size: 18px; margin: 12px 0; border: 1px solid #ccc; border-radius: 6px; text-align: center; }
        button { width: 100%; background: #1976d2; color: white; border: none; padding: 12px; font-size: 16px; font-weight: bold; border-radius: 6px; cursor: pointer; }
        .error { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
        .hint { color: #666; font-size: 12px; margin-top: 12px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Head Teacher / Admin Login</h2>
        <p style="color:#555; font-size:14px;">Enter your numeric Admin Number to access the dashboard.</p>

        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}

        <form method="POST" action="/admin/login">
            <input type="number" inputmode="numeric" pattern="[0-9]*" name="admin_number" placeholder="Enter Admin Number" required autofocus>
            <button type="submit">Continue to Dashboard</button>
        </form>

        <div class="hint">Default demo number: {{ default_number }}</div>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Salama Head Teacher Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f4f7f6; margin: 0; color: #222; }
        .container { max-width: 1020px; margin: auto; }
        .header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 20px; }
        .header h2 { margin: 0; }
        .actions { display: flex; flex-wrap: wrap; gap: 8px; }
        .actions a, .actions button { padding: 10px 14px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: bold; border: none; cursor: pointer; }
        .btn-primary { background: #1976d2; color: white; }
        .btn-sweep { background: #e65100; color: white; }
        .btn-danger { background: #c62828; color: white; }
        .btn-logout { background: #546e7a; color: white; }
        .btn-sm { padding: 6px 10px; font-size: 12px; border-radius: 5px; border: none; cursor: pointer; font-weight: bold; background: #e3f2fd; color: #1565c0; }
        .btn-call { padding: 6px 10px; font-size: 12px; border-radius: 5px; border: none; cursor: pointer; font-weight: bold; background: #fff3e0; color: #e65100; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 16px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }
        .stat-num { font-size: 26px; font-weight: bold; color: #1976d2; }
        .stat-label { font-size: 13px; color: #555; margin-top: 4px; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-bottom: 20px; overflow-x: auto; }
        .toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
        .toggle-box { display: flex; align-items: center; gap: 10px; background: #f8fafc; padding: 10px 14px; border-radius: 8px; border: 1px solid #e2e8f0; }
        select, input[type="text"] { padding: 7px 10px; border-radius: 6px; border: 1px solid #ccc; font-size: 13px; }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { text-align: left; padding: 11px; border-bottom: 1px solid #eee; font-size: 14px; }
        th { background: #f8fafc; color: #333; }
        .badge { padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: bold; display: inline-block; }
        .badge-ok { background: #d4edda; color: #155724; }
        .badge-warn { background: #fff3cd; color: #856404; }
        .badge-due { background: #fdecea; color: #b71c1c; }
        .badge-excused { background: #e0f2f1; color: #00695c; }
        .badge-lang { background: #ede7f6; color: #4527a0; }
        .empty { text-align: center; color: #666; padding: 20px; }
        .notice { background: #e8f5e9; color: #1b5e20; padding: 12px 14px; border-radius: 8px; margin-bottom: 14px; font-weight: bold; font-size: 14px; border-left: 4px solid #2e7d32; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h2>Salama Head Teacher Dashboard</h2>
                <small style="color:#666;">Live gate attendance, multilingual SMS roll-call alerts, USSD excused absences & parent callbacks</small>
            </div>
            <div class="actions">
                <form method="POST" action="/admin/roll-call-sweep" style="display:inline;" onsubmit="return confirm('Send urgent multilingual Absentee Safety SMS alerts for all unexcused missing students?');">
                    <button type="submit" class="btn-sweep">🚨 Run Morning Roll-Call Sweep</button>
                </form>
                <a class="btn-primary" href="/dashboard">↻ Refresh</a>
                <form method="POST" action="/admin/clear-checkins" style="display:inline;" onsubmit="return confirm('Clear all test logs?');">
                    <button type="submit" class="btn-danger">🗑 Clear Logs</button>
                </form>
                <a class="btn-logout" href="/admin/logout">Logout</a>
            </div>
        </div>

        {% if notice %}
            <div class="notice">{{ notice }}</div>
        {% endif %}

        <div class="stats">
            <div class="stat-card">
                <div class="stat-num" id="checked-in-count">{{ unique_checked_in }}</div>
                <div class="stat-label">Checked In Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-num">{{ total_students }}</div>
                <div class="stat-label">Total Students</div>
            </div>
            <div class="stat-card">
                <div class="stat-num" id="remaining-count" style="color:#e65100;">{{ remaining }}</div>
                <div class="stat-label">Unaccounted For</div>
            </div>
            <div class="stat-card">
                <div class="stat-num" style="color:#b71c1c;">{{ balance_due_count }}</div>
                <div class="stat-label">Students With Fee Balance</div>
            </div>
        </div>

        <div class="card">
            <div class="toolbar">
                <form method="POST" action="/admin/settings/fee-reminder" class="toggle-box">
                    <input
                        type="checkbox"
                        id="daily_fee_reminder"
                        name="daily_fee_reminder"
                        onchange="this.form.submit()"
                        {{ 'checked' if daily_fee_reminder else '' }}
                    >
                    <label for="daily_fee_reminder" style="font-size:14px; font-weight:bold; cursor:pointer;">
                        Include Daily Fee Reminder in Parent Check-In SMS
                    </label>
                </form>

                <form method="POST" action="/admin/manual-checkin" style="display:flex; gap:8px; align-items:center;">
                    <select name="student_id" required>
                        <option value="">Manual Check-In (Lost QR)...</option>
                        {% for sid, s in students.items() %}
                            <option value="{{ sid }}">{{ sid }} — {{ s.name }} ({{ s.class }})</option>
                        {% endfor %}
                    </select>
                    <button type="submit" class="btn-primary" style="padding:8px 14px;">Check In</button>
                </form>
            </div>

            <div class="toolbar" style="margin-bottom:0;">
                <h3 style="margin:0;">Recent Check-Ins (<span id="total-scans">{{ checkins|length }}</span>)</h3>
                <div style="display:flex; gap:8px; align-items:center;">
                    <label for="fee-filter" style="font-size:13px; color:#555;">Fee Filter:</label>
                    <select id="fee-filter" onchange="renderFilteredRows()">
                        <option value="ALL">All Fee Statuses</option>
                        <option value="Cleared">Cleared Only</option>
                        <option value="Balance Due">Balance Due Only</option>
                    </select>
                </div>
            </div>

            {% if checkins %}
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Student</th>
                            <th>ID & Class</th>
                            <th>Fees Status</th>
                            <th>Parent SMS</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="checkin-rows"></tbody>
                </table>
            {% else %}
                <div class="empty">No check-ins recorded yet. Scan a QR code on the gate device or use Manual Check-In above.</div>
            {% endif %}
        </div>

        <div class="card">
            <div class="toolbar">
                <div>
                    <h3 style="margin:0;">Not Yet Checked In ({{ missing_students|length }})</h3>
                    <small style="color:#666;">Switch parent SMS language anytime, send a direct safety alert, or view USSD sick/excused reports</small>
                </div>
            </div>
            {% if missing_students %}
                <table>
                    <thead>
                        <tr>
                            <th>Student</th>
                            <th>Status</th>
                            <th>Parent Phone</th>
                            <th>Preferred Language</th>
                            <th>Safety Alert Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for m in missing_students %}
                        <tr>
                            <td><strong>{{ m.name }}</strong> ({{ m.student_id }} · {{ m.class }})</td>
                            <td>
                                {% if m.excused %}
                                    <span class="badge badge-excused">Excused / Sick ({{ m.excused_time }})</span>
                                {% else %}
                                    <span class="badge badge-due">Missing</span>
                                {% endif %}
                            </td>
                            <td>{{ m.parent_phone }}</td>
                            <td>
                                <form method="POST" action="/admin/set-language" style="display:inline-flex; gap:6px; align-items:center;">
                                    <input type="hidden" name="student_id" value="{{ m.student_id }}">
                                    <select name="lang" onchange="this.form.submit()">
                                        <option value="en" {{ 'selected' if m.preferred_lang == 'en' else '' }}>English</option>
                                        <option value="lg" {{ 'selected' if m.preferred_lang == 'lg' else '' }}>Luganda</option>
                                        <option value="nyn" {{ 'selected' if m.preferred_lang == 'nyn' else '' }}>Runyankole</option>
                                        <option value="ach" {{ 'selected' if m.preferred_lang == 'ach' else '' }}>Acholi</option>
                                    </select>
                                </form>
                            </td>
                            <td>
                                <form method="POST" action="/admin/alert-missing-one" style="display:inline;">
                                    <input type="hidden" name="student_id" value="{{ m.student_id }}">
                                    <button type="submit" class="btn-call">📩 Send Safety Alert SMS</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% else %}
                <div class="empty">All registered students have checked in today!</div>
            {% endif %}
        </div>

        {% if absentee_alerts %}
        <div class="card">
            <h3 style="margin-top:0;">Roll-Call Safety Alerts Sent ({{ absentee_alerts|length }})</h3>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Student</th>
                        <th>Parent Phone</th>
                        <th>Language</th>
                        <th>SMS Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for a in absentee_alerts %}
                    <tr>
                        <td>{{ a.time }}</td>
                        <td><strong>{{ a.student_name }}</strong> ({{ a.student_id }} · {{ a.class }})</td>
                        <td>{{ a.parent_phone }}</td>
                        <td><span class="badge badge-lang">{{ a.lang_label }}</span></td>
                        <td><span class="badge badge-ok">{{ a.sms_status }}</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        <div class="card">
            <h3 style="margin-top:0;">Parent USSD Callback Requests ({{ callbacks|length }})</h3>
            {% if callbacks %}
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Student</th>
                            <th>Parent Phone</th>
                            <th>Language</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for cb in callbacks %}
                        <tr>
                            <td>{{ cb.time }}</td>
                            <td><strong>{{ cb.student_name }}</strong> ({{ cb.student_id }} · {{ cb.class }})</td>
                            <td>{{ cb.parent_phone }}</td>
                            <td><span class="badge badge-lang">{{ cb.lang_label }}</span></td>
                            <td><span class="badge badge-warn">Callback Requested</span></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% else %}
                <div class="empty">No parent callback requests via USSD yet.</div>
            {% endif %}
        </div>
    </div>

    <script>
        let latestCheckins = {{ checkins | tojson }};
        const langShortMap = {{ lang_short | tojson }};

        function formatUgx(amount) {
            return "UGX " + Number(amount || 0).toLocaleString();
        }

        function renderFilteredRows() {
            const tbody = document.getElementById('checkin-rows');
            if (!tbody) return;

            const filterVal = document.getElementById('fee-filter').value;
            const filtered = latestCheckins.filter(item => {
                if (filterVal === 'ALL') return true;
                return item.fee_status === filterVal;
            });

            if (filtered.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#666;">No matching check-ins for this filter.</td></tr>`;
                return;
            }

            tbody.innerHTML = filtered.map(item => {
                const feeBadge = item.fee_status === 'Cleared'
                    ? `<span class="badge badge-ok">Cleared</span>`
                    : `<span class="badge badge-due">Balance Due (${formatUgx(item.fee_balance)})</span>`;

                const smsBadge = item.sms_status.startsWith('Sent')
                    ? `<span class="badge badge-ok">${item.sms_status}</span>`
                    : `<span class="badge badge-warn">${item.sms_status}</span>`;

                const shortCode = langShortMap[item.lang] || 'EN';

                return `
                    <tr>
                        <td>${item.time}</td>
                        <td><strong>${item.name}</strong></td>
                        <td>${item.student_id} · ${item.class}</td>
                        <td>${feeBadge}</td>
                        <td>${smsBadge}<small style="color:#666;"> · ${shortCode}</small></td>
                        <td>
                            <form method="POST" action="/admin/resend-sms" style="display:inline;">
                                <input type="hidden" name="student_id" value="${item.student_id}">
                                <button type="submit" class="btn-sm">Resend SMS</button>
                            </form>
                        </td>
                    </tr>
                `;
            }).join('');
        }

        renderFilteredRows();

        setInterval(async () => {
            try {
                const res = await fetch('/api/checkins');
                if (!res.ok) return;
                const data = await res.json();
                latestCheckins = data.checkins || [];
                document.getElementById('checked-in-count').textContent = data.unique_checked_in;
                document.getElementById('remaining-count').textContent = data.remaining;
                const totalScansEl = document.getElementById('total-scans');
                if (totalScansEl) totalScansEl.textContent = latestCheckins.length;
                renderFilteredRows();
            } catch (e) {
                // Ignore transient polling errors
            }
        }, 4000);
    </script>
</body>
</html>
"""


def is_admin_authenticated():
    return bool(session.get("is_admin"))


def get_today_key(student_id):
    today_str = datetime.now().strftime("%Y-%m-%d")
    return (today_str, student_id)


def find_students_by_parent_phone(phone_number):
    cleaned = (phone_number or "").strip()
    return [
        (sid, info)
        for sid, info in STUDENTS_DB.items()
        if info.get("parent_phone", "").strip() == cleaned
    ]


def build_parent_sms_message(student, now_str, include_fee_reminder=False):
    lang = student.get("preferred_lang", "en")
    has_balance = student.get("fee_status") == "Balance Due" and student.get("fee_balance", 0) > 0
    balance_fmt = f"UGX {student.get('fee_balance', 0):,}"

    if lang == "lg":
        msg = (
            f"Salama: Omwana wo {student['name']} ({student['class']}) "
            f"atuuse bulungi ku ssomero ku ssaawa {now_str}."
        )
        if include_fee_reminder and has_balance:
            msg += f" Okujjukiza ku bisale: Obanjibwa {balance_fmt}."
        return msg

    if lang == "nyn":
        msg = (
            f"Salama: Omwana waawe {student['name']} ({student['class']}) "
            f"ahikire gye aha ishomero shaaha {now_str}."
        )
        if include_fee_reminder and has_balance:
            msg += f" Okwijutsya kw'ebicweka: Oine ebisharwa bya {balance_fmt}."
        return msg

    if lang == "ach":
        msg = (
            f"Salama: Latinni {student['name']} ({student['class']}) "
            f"oo maber i gang kwan i cawa {now_str}."
        )
        if include_fee_reminder and has_balance:
            msg += f" Wi po me cul: Pwod tye ki cul me {balance_fmt}."
        return msg

    msg = (
        f"Salama Alert: Your child {student['name']} ({student['class']}) "
        f"safely checked in at school at {now_str}."
    )
    if include_fee_reminder and has_balance:
        msg += f" Daily Fee Reminder: Outstanding balance is {balance_fmt}."
    return msg


def build_absentee_sms_message(student, now_str):
    lang = student.get("preferred_lang", "en")
    if lang == "lg":
        return (
            f"SALAMA OBUBAKA OBW'AMANGU: Omwana wo {student['name']} ({student['class']}) "
            f"tannatuuka ku ssomero okutuuka ku ssaawa {now_str}. Kuba ku ssomero oba nyiga *384*42301# okutegeeza."
        )
    if lang == "nyn":
        return (
            f"SALAMA OKWEJUTSYA KW'OBURINZI: Omwana waawe {student['name']} ({student['class']}) "
            f"takahikire aha ishomero okuhika shaaha {now_str}. Teerera ishomero ninga oshabe *384*42301#."
        )
    if lang == "ach":
        return (
            f"SALAMA KWENA ME GWOKO LATIN: Latinni {student['name']} ({student['class']}) "
            f"peya oo i gang kwan nio i cawa {now_str}. Goy cim i gang kwan onyo di *384*42301#."
        )
    return (
        f"SALAMA SAFETY ALERT: Your child {student['name']} ({student['class']}) "
        f"has NOT checked in at school as of {now_str}. Contact the school or dial *384*42301# to report an absence."
    )


def send_checkin_sms(student, now_str):
    include_reminder = DASHBOARD_SETTINGS.get("daily_fee_reminder", False)
    message = build_parent_sms_message(student, now_str, include_fee_reminder=include_reminder)
    try:
        response = sms.send(message, [student["parent_phone"]])
        print("SMS Response:", response)
        return "Sent + Fee Note" if include_reminder and student.get("fee_balance", 0) > 0 else "Sent"
    except Exception as e:
        print("SMS Error:", e)
        return "Logged (Sandbox/Check Key)"


def trigger_absentee_alert(student_id, student):
    now_str = datetime.now().strftime("%I:%M:%S %p")
    lang = student.get("preferred_lang", "en")
    sms_text = build_absentee_sms_message(student, now_str)
    try:
        sms_resp = sms.send(sms_text, [student["parent_phone"]])
        print("Absentee SMS Response:", sms_resp)
        sms_status = "Sent"
    except Exception as e:
        print("Absentee SMS Error:", e)
        sms_status = "SMS Error"

    ABSENTEE_ALERTS.insert(0, {
        "student_id": student_id,
        "student_name": student["name"],
        "class": student["class"],
        "parent_phone": student["parent_phone"],
        "lang": lang,
        "lang_label": LANG_LABELS.get(lang, "English"),
        "sms_status": sms_status,
        "time": now_str,
    })
    return sms_status


def try_record_checkin(student_id, student, source="QR Scan"):
    day_key = get_today_key(student_id)
    if day_key in DAILY_CHECKED_IN:
        first_time = DAILY_CHECKED_IN[day_key]
        return False, first_time, None

    now = datetime.now().strftime("%I:%M:%S %p")
    sms_status = send_checkin_sms(student, now)
    DAILY_CHECKED_IN[day_key] = now
    DAILY_EXCUSED.pop(day_key, None)

    CHECKINS.insert(0, {
        "student_id": student_id,
        "name": student["name"],
        "class": student["class"],
        "parent_phone": student["parent_phone"],
        "lang": student.get("preferred_lang", "en"),
        "fee_status": student.get("fee_status", "Cleared"),
        "fee_balance": student.get("fee_balance", 0),
        "source": source,
        "time": now,
        "sms_status": sms_status,
    })
    return True, now, sms_status


def get_missing_students():
    today_str = datetime.now().strftime("%Y-%m-%d")
    missing = []
    for sid, info in STUDENTS_DB.items():
        if (today_str, sid) not in DAILY_CHECKED_IN:
            excused_info = DAILY_EXCUSED.get((today_str, sid))
            missing.append({
                "student_id": sid,
                "name": info["name"],
                "class": info["class"],
                "parent_phone": info["parent_phone"],
                "preferred_lang": info.get("preferred_lang", "en"),
                "excused": bool(excused_info),
                "excused_time": excused_info["time"] if excused_info else "",
            })
    return missing


def build_dashboard_summary():
    total_students = len(STUDENTS_DB)
    today_str = datetime.now().strftime("%Y-%m-%d")
    unique_checked_in = sum(1 for (d, _) in DAILY_CHECKED_IN if d == today_str)
    unique_excused = sum(
        1 for (d, sid) in DAILY_EXCUSED
        if d == today_str and (today_str, sid) not in DAILY_CHECKED_IN
    )
    remaining = max(total_students - unique_checked_in - unique_excused, 0)
    balance_due_count = sum(
        1 for s in STUDENTS_DB.values() if s.get("fee_status") == "Balance Due"
    )
    return total_students, unique_checked_in, remaining, balance_due_count


@app.route("/", methods=["GET"])
def index():
    return render_template_string(SCANNER_HTML)


@app.route("/scan", methods=["POST"])
def scan():
    student_id = request.form.get("student_id", "").strip().upper()
    student = STUDENTS_DB.get(student_id)

    if not student:
        return render_template_string(
            SCANNER_HTML,
            message=f"Unrecognized ID: {student_id}",
            status="error",
        )

    created, timestamp, _ = try_record_checkin(student_id, student, source="QR Scan")
    if not created:
        return render_template_string(
            SCANNER_HTML,
            message=f"{student['name']} ({student_id}) is already registered today at {timestamp}. Duplicate check-in blocked.",
            status="warning",
        )

    success_msg = f"Checked In: {student['name']} ({student['class']}) at {timestamp}."
    return render_template_string(SCANNER_HTML, message=success_msg, status="success")


@app.route("/ussd", methods=["POST"])
def ussd():
    phone_number = request.form.get("phoneNumber", "").strip()
    text = request.form.get("text", "").strip()
    parts = [p for p in text.split("*") if p != ""]

    matches = find_students_by_parent_phone(phone_number)
    if not matches:
        return Response(
            "END Salama: No student linked to this number / Tewali muyizi ku nnamba eno.",
            mimetype="text/plain",
        )

    student_id, student = matches[0]
    today_str = datetime.now().strftime("%Y-%m-%d")
    checkin_time = DAILY_CHECKED_IN.get((today_str, student_id))

    # Step 1: Language selection
    if len(parts) == 0:
        welcome = (
            "CON Salama Parent Desk\n"
            "1. English\n"
            "2. Luganda\n"
            "3. Runyankole\n"
            "4. Acholi"
        )
        return Response(welcome, mimetype="text/plain")

    lang_map = {
        "1": "en",
        "2": "lg",
        "3": "nyn",
        "4": "ach",
    }
    lang = lang_map.get(parts[0])
    if not lang:
        return Response(
            "END Invalid selection. Please dial again.",
            mimetype="text/plain",
        )

    # Persist the parent's chosen language so future SMS alerts match
    student["preferred_lang"] = lang

    # Step 2: Main menu in chosen language
    if len(parts) == 1:
        if lang == "lg":
            menu = (
                f"CON Salama ({student['name']} - {student['class']})\n"
                "1. Okutuuka kw'omwana leero\n"
                "2. Ebisale by'essomero (Fees)\n"
                "3. Saba essomero likukubire\n"
                "4. Tegeeza omwana mulwadde"
            )
        elif lang == "nyn":
            menu = (
                f"CON Salama ({student['name']} - {student['class']})\n"
                "1. Okuhika kw'omwana erizooba\n"
                "2. Ebicweka by'ishomero (Fees)\n"
                "3. Shaba ishomero rikuteerere\n"
                "4. Gamba ngu omwana arwaire"
            )
        elif lang == "ach":
            menu = (
                f"CON Salama ({student['name']} - {student['class']})\n"
                "1. Tuno pa latin tin\n"
                "2. Cul me gang kwan (Fees)\n"
                "3. Penyo me miyo cim\n"
                "4. Tit ni latin two"
            )
        else:
            menu = (
                f"CON Salama ({student['name']} - {student['class']})\n"
                "1. Today's Gate Check-In Status\n"
                "2. School Fees Balance\n"
                "3. Request School Callback\n"
                "4. Report Child Sick / Excused"
            )
        return Response(menu, mimetype="text/plain")

    # Step 3: Action response in chosen language
    action = parts[1]
    is_cleared = student.get("fee_status") == "Cleared" or student.get("fee_balance", 0) == 0
    bal = f"UGX {student.get('fee_balance', 0):,}"

    if action == "1":
        if lang == "lg":
            res = (
                f"END {student['name']} ({student['class']}) atuuse ku ssomero leero ku ssaawa {checkin_time}."
                if checkin_time
                else f"END {student['name']} ({student['class']}) tannatuuka ku ssomero leero."
            )
        elif lang == "nyn":
            res = (
                f"END {student['name']} ({student['class']}) ahikire aha ishomero erizooba shaaha {checkin_time}."
                if checkin_time
                else f"END {student['name']} ({student['class']}) takahikire aha ishomero erizooba."
            )
        elif lang == "ach":
            res = (
                f"END {student['name']} ({student['class']}) oo i gang kwan tin i cawa {checkin_time}."
                if checkin_time
                else f"END {student['name']} ({student['class']}) peya oo i gang kwan tin."
            )
        else:
            res = (
                f"END {student['name']} ({student['class']}) checked in today at {checkin_time}."
                if checkin_time
                else f"END {student['name']} ({student['class']}) has NOT checked in yet today."
            )
        return Response(res, mimetype="text/plain")

    if action == "2":
        if lang == "lg":
            res = (
                f"END {student['name']} ({student['class']}): Ebisale by'essomero byawedde (UGX 0)."
                if is_cleared
                else f"END {student['name']} ({student['class']}): Obanjibwa ebisale bya {bal}."
            )
        elif lang == "nyn":
            res = (
                f"END {student['name']} ({student['class']}): Ebicweka by'ishomero bihendukire (UGX 0)."
                if is_cleared
                else f"END {student['name']} ({student['class']}): Oine ebisharwa bya {bal}."
            )
        elif lang == "ach":
            res = (
                f"END {student['name']} ({student['class']}): Cul me gang kwan otum woko (UGX 0)."
                if is_cleared
                else f"END {student['name']} ({student['class']}): Pwod tye ki cul me {bal}."
            )
        else:
            res = (
                f"END {student['name']} ({student['class']}): School fees are CLEARED (UGX 0)."
                if is_cleared
                else f"END {student['name']} ({student['class']}): Fee Balance Due is {bal}."
            )
        return Response(res, mimetype="text/plain")

    if action == "3":
        now_str = datetime.now().strftime("%I:%M:%S %p")
        CALLBACK_REQUESTS.insert(0, {
            "student_id": student_id,
            "student_name": student["name"],
            "class": student["class"],
            "parent_phone": phone_number,
            "lang": lang,
            "lang_label": LANG_LABELS.get(lang, "English"),
            "time": now_str,
        })
        if lang == "lg":
            res = f"END Okusaba kwo kuweerezeddwa ku lwa {student['name']}. Essomero lijja kukukubira mangu."
        elif lang == "nyn":
            res = f"END Okushaba kwawe kwahika ahabwa {student['name']}. Ishomero niriija kukuteerera bwanyima."
        elif lang == "ach":
            res = f"END Penyo ni ocwalo pi {student['name']}. Gang kwan bi goyo cim boti oyot."
        else:
            res = f"END Callback requested for {student['name']}. The school office will contact you shortly."
        return Response(res, mimetype="text/plain")

    if action == "4":
        now_str = datetime.now().strftime("%I:%M:%S %p")
        DAILY_EXCUSED[(today_str, student_id)] = {
            "time": now_str,
            "lang_label": LANG_LABELS.get(lang, "English"),
        }
        if lang == "lg":
            res = f"END Webale okutegeeza. {student['name']} awandiikiddwa ng'omulwadde/alina olukusa leero."
        elif lang == "nyn":
            res = f"END Webare kugamba. {student['name']} yaahandiikwa nk'orwaire erizooba."
        elif lang == "ach":
            res = f"END Apwoyo tito. {student['name']} kicoyo ni two / tye ki twero tin."
        else:
            res = f"END Thank you. {student['name']} has been marked as Excused (Sick) on the Head Teacher dashboard."
        return Response(res, mimetype="text/plain")

    invalid_messages = {
        "lg": "END Ekyalondeddwa tekiriimu. Ddamu okube.",
        "nyn": "END Eki waatoorana tikiriho. Garuka oteere.",
        "ach": "END Gin ma i yero pe tye. Tem doki.",
        "en": "END Invalid selection. Please dial again.",
    }
    return Response(invalid_messages.get(lang, invalid_messages["en"]), mimetype="text/plain")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        entered_number = request.form.get("admin_number", "").strip()
        if not entered_number.isdigit():
            return render_template_string(
                ADMIN_LOGIN_HTML,
                error="Please enter numbers only for your Admin Number.",
                default_number=ADMIN_NUMBER,
            )
        if entered_number == str(ADMIN_NUMBER):
            session["is_admin"] = True
            return redirect(url_for("dashboard"))
        return render_template_string(
            ADMIN_LOGIN_HTML,
            error="Invalid Admin Number. Please try again.",
            default_number=ADMIN_NUMBER,
        )

    return render_template_string(
        ADMIN_LOGIN_HTML,
        error=None,
        default_number=ADMIN_NUMBER,
    )


@app.route("/admin/logout", methods=["GET"])
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/settings/fee-reminder", methods=["POST"])
def toggle_fee_reminder():
    if not is_admin_authenticated():
        return redirect(url_for("admin_login"))
    DASHBOARD_SETTINGS["daily_fee_reminder"] = bool(request.form.get("daily_fee_reminder"))
    state_label = "enabled" if DASHBOARD_SETTINGS["daily_fee_reminder"] else "disabled"
    session["dashboard_notice"] = f"Daily fee reminder in parent SMS {state_label}."
    return redirect(url_for("dashboard"))


@app.route("/admin/set-language", methods=["POST"])
def set_student_language():
    if not is_admin_authenticated():
        return redirect(url_for("admin_login"))
    student_id = request.form.get("student_id", "").strip().upper()
    lang = request.form.get("lang", "en").strip()
    student = STUDENTS_DB.get(student_id)
    if student and lang in LANG_LABELS:
        student["preferred_lang"] = lang
        session["dashboard_notice"] = f"Updated {student['name']}'s parent SMS language to {LANG_LABELS[lang]}."
    return redirect(url_for("dashboard"))


@app.route("/admin/alert-missing-one", methods=["POST"])
def alert_missing_one():
    if not is_admin_authenticated():
        return redirect(url_for("admin_login"))
    student_id = request.form.get("student_id", "").strip().upper()
    student = STUDENTS_DB.get(student_id)
    if not student:
        session["dashboard_notice"] = "Student not found."
        return redirect(url_for("dashboard"))
    sms_status = trigger_absentee_alert(student_id, student)
    session["dashboard_notice"] = (
        f"Absentee Safety SMS dispatched for {student['name']} ({student['parent_phone']}) "
        f"in {LANG_LABELS.get(student.get('preferred_lang', 'en'), 'English')}: {sms_status}."
    )
    return redirect(url_for("dashboard"))


@app.route("/admin/roll-call-sweep", methods=["POST"])
def roll_call_sweep():
    if not is_admin_authenticated():
        return redirect(url_for("admin_login"))
    unexcused_missing = [m for m in get_missing_students() if not m["excused"]]
    if not unexcused_missing:
        session["dashboard_notice"] = "Roll-Call Sweep complete: All students are either checked in or excused!"
        return redirect(url_for("dashboard"))

    for item in unexcused_missing:
        sid = item["student_id"]
        trigger_absentee_alert(sid, STUDENTS_DB[sid])

    session["dashboard_notice"] = (
        f"Morning Roll-Call Sweep complete: Dispatched multilingual Absentee Safety SMS alerts "
        f"for {len(unexcused_missing)} unaccounted student(s)."
    )
    return redirect(url_for("dashboard"))


@app.route("/admin/manual-checkin", methods=["POST"])
def manual_checkin():
    if not is_admin_authenticated():
        return redirect(url_for("admin_login"))
    student_id = request.form.get("student_id", "").strip().upper()
    student = STUDENTS_DB.get(student_id)
    if not student:
        session["dashboard_notice"] = f"Could not find student {student_id}."
        return redirect(url_for("dashboard"))
    created, timestamp, _ = try_record_checkin(student_id, student, source="Admin Manual")
    if not created:
        session["dashboard_notice"] = f"{student['name']} ({student_id}) is already registered today at {timestamp}."
        return redirect(url_for("dashboard"))
    session["dashboard_notice"] = f"Manually checked in {student['name']} ({student_id}) at {timestamp}."
    return redirect(url_for("dashboard"))


@app.route("/admin/resend-sms", methods=["POST"])
def resend_sms():
    if not is_admin_authenticated():
        return redirect(url_for("admin_login"))
    student_id = request.form.get("student_id", "").strip().upper()
    student = STUDENTS_DB.get(student_id)
    if not student:
        session["dashboard_notice"] = "Student record not found."
        return redirect(url_for("dashboard"))
    now_str = datetime.now().strftime("%I:%M:%S %p")
    status = send_checkin_sms(student, now_str)
    session["dashboard_notice"] = f"SMS action for {student['name']}: {status}."
    return redirect(url_for("dashboard"))


@app.route("/admin/clear-checkins", methods=["POST"])
def clear_checkins():
    if not is_admin_authenticated():
        return redirect(url_for("admin_login"))
    CHECKINS.clear()
    DAILY_CHECKED_IN.clear()
    DAILY_EXCUSED.clear()
    CALLBACK_REQUESTS.clear()
    ABSENTEE_ALERTS.clear()
    session["dashboard_notice"] = "All test check-ins, excused statuses, callback logs, and absentee alerts have been cleared."
    return redirect(url_for("dashboard"))


def render_dashboard():
    notice = session.pop("dashboard_notice", None)
    total_students, unique_checked_in, remaining, balance_due_count = build_dashboard_summary()
    return render_template_string(
        DASHBOARD_HTML,
        checkins=CHECKINS,
        students=STUDENTS_DB,
        missing_students=get_missing_students(),
        absentee_alerts=ABSENTEE_ALERTS,
        callbacks=CALLBACK_REQUESTS,
        lang_short=LANG_SHORT,
        total_students=total_students,
        unique_checked_in=unique_checked_in,
        remaining=remaining,
        balance_due_count=balance_due_count,
        daily_fee_reminder=DASHBOARD_SETTINGS.get("daily_fee_reminder", False),
        notice=notice,
    )


@app.route("/dashboard", methods=["GET"])
def dashboard():
    if not is_admin_authenticated():
        return redirect(url_for("admin_login"))
    return render_dashboard()


@app.route("/api/checkins", methods=["GET"])
def api_checkins():
    if not is_admin_authenticated():
        return jsonify({"error": "Unauthorized"}), 401
    total_students, unique_checked_in, remaining, balance_due_count = build_dashboard_summary()
    return jsonify({
        "checkins": CHECKINS,
        "callbacks": CALLBACK_REQUESTS,
        "absentee_alerts": ABSENTEE_ALERTS,
        "total_students": total_students,
        "unique_checked_in": unique_checked_in,
        "remaining": remaining,
        "balance_due_count": balance_due_count,
        "daily_fee_reminder": DASHBOARD_SETTINGS.get("daily_fee_reminder", False),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)