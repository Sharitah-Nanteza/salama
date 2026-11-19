import os
from datetime import datetime
from flask import (
    Flask,
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
        "fee_status": "Cleared",
        "fee_balance": 0,
    },
    "STU-002": {
        "name": "Muwonge Daniel",
        "class": "P.4",
        "parent_phone": "+256700000002",
        "fee_status": "Balance Due",
        "fee_balance": 120000,
    },
    "STU-003": {
        "name": "Nakato Faith",
        "class": "P.5",
        "parent_phone": "+256700000003",
        "fee_status": "Balance Due",
        "fee_balance": 85000,
    },
    "STU-004": {
        "name": "Okello Brian",
        "class": "P.7",
        "parent_phone": "+256700000004",
        "fee_status": "Cleared",
        "fee_balance": 0,
    },
    "STU-005": {
        "name": "Byaruhanga Grace",
        "class": "P.3",
        "parent_phone": "+256700000005",
        "fee_status": "Balance Due",
        "fee_balance": 45000,
    },
}

# Stores check-in entries in memory for the live session
CHECKINS = []

# Maps (YYYY-MM-DD, student_id) -> check-in time string so each student only checks in once per day
DAILY_CHECKED_IN = {}

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
        .container { max-width: 960px; margin: auto; }
        .header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 20px; }
        .header h2 { margin: 0; }
        .actions { display: flex; flex-wrap: wrap; gap: 8px; }
        .actions a, .actions button { padding: 10px 14px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: bold; border: none; cursor: pointer; }
        .btn-primary { background: #1976d2; color: white; }
        .btn-danger { background: #c62828; color: white; }
        .btn-logout { background: #546e7a; color: white; }
        .btn-sm { padding: 6px 10px; font-size: 12px; border-radius: 5px; border: none; cursor: pointer; font-weight: bold; background: #e3f2fd; color: #1565c0; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 16px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }
        .stat-num { font-size: 26px; font-weight: bold; color: #1976d2; }
        .stat-label { font-size: 13px; color: #555; margin-top: 4px; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-bottom: 20px; overflow-x: auto; }
        .toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
        .toggle-box { display: flex; align-items: center; gap: 10px; background: #f8fafc; padding: 10px 14px; border-radius: 8px; border: 1px solid #e2e8f0; }
        select, input[type="text"] { padding: 8px 10px; border-radius: 6px; border: 1px solid #ccc; font-size: 14px; }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { text-align: left; padding: 11px; border-bottom: 1px solid #eee; font-size: 14px; }
        th { background: #f8fafc; color: #333; }
        .badge { padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: bold; display: inline-block; }
        .badge-ok { background: #d4edda; color: #155724; }
        .badge-warn { background: #fff3cd; color: #856404; }
        .badge-due { background: #fdecea; color: #b71c1c; }
        .empty { text-align: center; color: #666; padding: 20px; }
        .notice { background: #e8f5e9; color: #1b5e20; padding: 10px 14px; border-radius: 8px; margin-bottom: 14px; font-weight: bold; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h2>Salama Head Teacher Dashboard</h2>
                <small style="color:#666;">Live attendance, student fees status & parent SMS controls</small>
            </div>
            <div class="actions">
                <a class="btn-primary" href="/dashboard">↻ Refresh Now</a>
                <form method="POST" action="/admin/clear-checkins" style="display:inline;" onsubmit="return confirm('Clear all test check-in entries?');">
                    <button type="submit" class="btn-danger">🗑 Clear Test Log</button>
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
                <div class="stat-num" id="remaining-count">{{ remaining }}</div>
                <div class="stat-label">Not Yet Checked In</div>
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
    </div>

    <script>
        let latestCheckins = {{ checkins | tojson }};

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

                return `
                    <tr>
                        <td>${item.time}</td>
                        <td><strong>${item.name}</strong></td>
                        <td>${item.student_id} · ${item.class}</td>
                        <td>${feeBadge}</td>
                        <td>${smsBadge}</td>
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


def build_parent_sms_message(student, now_str, include_fee_reminder=False):
    msg = (
        f"Salama Alert: Your child {student['name']} ({student['class']}) "
        f"safely checked in at school at {now_str}."
    )
    if include_fee_reminder and student.get("fee_status") == "Balance Due" and student.get("fee_balance", 0) > 0:
        balance_fmt = f"UGX {student['fee_balance']:,}"
        msg += f" Daily Fee Reminder: Outstanding balance is {balance_fmt}."
    return msg


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


def try_record_checkin(student_id, student, source="QR Scan"):
    day_key = get_today_key(student_id)
    if day_key in DAILY_CHECKED_IN:
        first_time = DAILY_CHECKED_IN[day_key]
        return False, first_time, None

    now = datetime.now().strftime("%I:%M:%S %p")
    sms_status = send_checkin_sms(student, now)
    DAILY_CHECKED_IN[day_key] = now

    CHECKINS.insert(0, {
        "student_id": student_id,
        "name": student["name"],
        "class": student["class"],
        "parent_phone": student["parent_phone"],
        "fee_status": student.get("fee_status", "Cleared"),
        "fee_balance": student.get("fee_balance", 0),
        "source": source,
        "time": now,
        "sms_status": sms_status,
    })
    return True, now, sms_status


def build_dashboard_summary():
    total_students = len(STUDENTS_DB)
    today_str = datetime.now().strftime("%Y-%m-%d")
    unique_checked_in = sum(1 for (d, _) in DAILY_CHECKED_IN if d == today_str)
    remaining = max(total_students - unique_checked_in, 0)
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
    session["dashboard_notice"] = "All test check-in entries have been cleared."
    return redirect(url_for("dashboard"))


def render_dashboard():
    notice = session.pop("dashboard_notice", None)
    total_students, unique_checked_in, remaining, balance_due_count = build_dashboard_summary()
    return render_template_string(
        DASHBOARD_HTML,
        checkins=CHECKINS,
        students=STUDENTS_DB,
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
        "total_students": total_students,
        "unique_checked_in": unique_checked_in,
        "remaining": remaining,
        "balance_due_count": balance_due_count,
        "daily_fee_reminder": DASHBOARD_SETTINGS.get("daily_fee_reminder", False),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)