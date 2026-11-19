import os
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from dotenv import load_dotenv
import africastalking

load_dotenv()

app = Flask(__name__)

USERNAME = os.getenv("AT_USERNAME", "sandbox")
API_KEY = os.getenv("AT_API_KEY")

africastalking.initialize(USERNAME, API_KEY)
sms = africastalking.SMS

STUDENTS_DB = {
    "STU-001": {
        "name": "Namukasa Sarah",
        "class": "P.6",
        "parent_phone": "+256700000001"
    },
    "STU-002": {
        "name": "Muwonge Daniel",
        "class": "P.4",
        "parent_phone": "+256700000002"
    },
    "STU-003": {
        "name": "Nakato Faith",
        "class": "P.5",
        "parent_phone": "+256700000003"
    },
    "STU-004": {
        "name": "Okello Brian",
        "class": "P.7",
        "parent_phone": "+256700000004"
    },
    "STU-005": {
        "name": "Byaruhanga Grace",
        "class": "P.3",
        "parent_phone": "+256700000005"
    }
}

# Stores check-in entries in memory for the live session
CHECKINS = []

SCANNER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Salama Gate Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; background: #f4f7f6; margin: 0; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); max-width: 450px; margin: auto; }
        input { width: 80%; padding: 12px; font-size: 18px; margin: 10px 0; border: 1px solid #ccc; border-radius: 6px; }
        button { background: #2e7d32; color: white; border: none; padding: 12px 25px; font-size: 18px; border-radius: 6px; cursor: pointer; }
        .result { margin-top: 20px; padding: 15px; border-radius: 6px; font-weight: bold; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
        #reader { width: 100%; max-width: 350px; margin: auto; display: none; }
        .nav-link { display: inline-block; margin-top: 16px; color: #1976d2; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Salama Gate Check-In</h2>
        <p>Scan student ID QR code or type ID:</p>

        <button onclick="startScanner()" id="scan-btn" style="background: #1976d2; margin-bottom: 15px;">📷 Open Camera Scanner</button>
        <div id="reader"></div>

        <form method="POST" action="/scan" id="checkin-form">
            <input type="text" id="student_id" name="student_id" placeholder="e.g. STU-001" autofocus required><br>
            <button type="submit">Verify & Notify</button>
        </form>

        {% if message %}
            <div class="result {{ status }}">{{ message }}</div>
        {% endif %}

        <a class="nav-link" href="/dashboard">📊 View Live School Dashboard →</a>
    </div>

    <script>
        function startScanner() {
            document.getElementById('reader').style.display = 'block';
            document.getElementById('scan-btn').style.display = 'none';

            let html5QrCode = new Html5Qrcode("reader");

            function onScanSuccess(decodedText, decodedResult) {
                document.getElementById('student_id').value = decodedText.trim();
                document.getElementById('checkin-form').submit();
                html5QrCode.stop().catch(() => {});
            }

            html5QrCode.start(
                { facingMode: "environment" },
                { fps: 10, qrbox: { width: 250, height: 250 } },
                onScanSuccess
            ).catch(err => {
                alert("Camera access denied or unavailable. Use manual typing.");
            });
        }
    </script>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Salama Live Attendance Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f4f7f6; margin: 0; color: #222; }
        .container { max-width: 820px; margin: auto; }
        .header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 20px; }
        .header h2 { margin: 0; }
        .actions a, .actions button { padding: 10px 16px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: bold; border: none; cursor: pointer; }
        .btn-primary { background: #1976d2; color: white; }
        .btn-secondary { background: #2e7d32; color: white; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 16px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }
        .stat-num { font-size: 28px; font-weight: bold; color: #1976d2; }
        .stat-label { font-size: 13px; color: #555; margin-top: 4px; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #eee; font-size: 14px; }
        th { background: #f8fafc; color: #333; }
        .badge { padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: bold; }
        .badge-ok { background: #d4edda; color: #155724; }
        .badge-warn { background: #fff3cd; color: #856404; }
        .empty { text-align: center; color: #666; padding: 24px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h2>Salama Live Attendance Dashboard</h2>
                <small style="color:#666;">Real-time gate check-ins & parent SMS alerts</small>
            </div>
            <div class="actions">
                <a class="btn-secondary" href="/">📷 Gate Scanner</a>
                <button class="btn-primary" onclick="location.reload()">↻ Refresh Now</button>
            </div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-num" id="checked-in-count">{{ unique_checked_in }}</div>
                <div class="stat-label">Unique Students Checked In</div>
            </div>
            <div class="stat-card">
                <div class="stat-num">{{ total_students }}</div>
                <div class="stat-label">Total Rostered Students</div>
            </div>
            <div class="stat-card">
                <div class="stat-num" id="remaining-count">{{ remaining }}</div>
                <div class="stat-label">Not Yet Checked In</div>
            </div>
        </div>

        <div class="card">
            <h3 style="margin-top: 0;">Recent Check-Ins (<span id="total-scans">{{ checkins|length }}</span>)</h3>
            {% if checkins %}
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Student</th>
                            <th>ID</th>
                            <th>Class</th>
                            <th>Parent SMS</th>
                        </tr>
                    </thead>
                    <tbody id="checkin-rows">
                        {% for item in checkins %}
                        <tr>
                            <td>{{ item.time }}</td>
                            <td><strong>{{ item.name }}</strong></td>
                            <td>{{ item.student_id }}</td>
                            <td>{{ item.class }}</td>
                            <td>
                                <span class="badge {{ 'badge-ok' if item.sms_status == 'Sent' else 'badge-warn' }}">
                                    {{ item.sms_status }}
                                </span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% else %}
                <div class="empty">No check-ins recorded yet. Scan a QR code on your phone to see live updates here!</div>
            {% endif %}
        </div>
    </div>

    <script>
        // Poll every 4 seconds so teachers/judges see check-ins appear automatically
        setInterval(async () => {
            try {
                const res = await fetch('/api/checkins');
                if (!res.ok) return;
                const data = await res.json();
                document.getElementById('checked-in-count').textContent = data.unique_checked_in;
                document.getElementById('remaining-count').textContent = data.remaining;
                const totalScansEl = document.getElementById('total-scans');
                if (totalScansEl) totalScansEl.textContent = data.checkins.length;

                const tbody = document.getElementById('checkin-rows');
                if (tbody && data.checkins.length > 0) {
                    tbody.innerHTML = data.checkins.map(item => `
                        <tr>
                            <td>${item.time}</td>
                            <td><strong>${item.name}</strong></td>
                            <td>${item.student_id}</td>
                            <td>${item.class}</td>
                            <td><span class="badge ${item.sms_status === 'Sent' ? 'badge-ok' : 'badge-warn'}">${item.sms_status}</span></td>
                        </tr>
                    `).join('');
                }
            } catch (e) {
                // Ignore transient polling errors
            }
        }, 4000);
    </script>
</body>
</html>
"""

def build_dashboard_summary():
    total_students = len(STUDENTS_DB)
    unique_ids = {entry["student_id"] for entry in CHECKINS}
    unique_checked_in = len(unique_ids)
    remaining = max(total_students - unique_checked_in, 0)
    return total_students, unique_checked_in, remaining

@app.route("/", methods=["GET"])
def index():
    return render_template_string(SCANNER_HTML)

@app.route("/scan", methods=["POST"])
def scan():
    student_id = request.form.get("student_id", "").strip().upper()
    student = STUDENTS_DB.get(student_id)

    if not student:
        return render_template_string(SCANNER_HTML, message=f"Unrecognized ID: {student_id}", status="error")

    now = datetime.now().strftime("%I:%M:%S %p")
    message = f"Salama Alert: Your child {student['name']} ({student['class']}) safely checked in at school at {now}."

    sms_status = "Sent"
    try:
        response = sms.send(message, [student["parent_phone"]])
        print("SMS Response:", response)
    except Exception as e:
        print("SMS Error:", e)
        sms_status = "Logged (Sandbox/Check Key)"

    CHECKINS.insert(0, {
        "student_id": student_id,
        "name": student["name"],
        "class": student["class"],
        "parent_phone": student["parent_phone"],
        "time": now,
        "sms_status": sms_status
    })

    success_msg = f"Checked In: {student['name']} ({student['class']}) at {now}."
    return render_template_string(SCANNER_HTML, message=success_msg, status="success")

@app.route("/dashboard", methods=["GET"])
def dashboard():
    total_students, unique_checked_in, remaining = build_dashboard_summary()
    return render_template_string(
        DASHBOARD_HTML,
        checkins=CHECKINS,
        total_students=total_students,
        unique_checked_in=unique_checked_in,
        remaining=remaining
    )

@app.route("/api/checkins", methods=["GET"])
def api_checkins():
    total_students, unique_checked_in, remaining = build_dashboard_summary()
    return jsonify({
        "checkins": CHECKINS,
        "total_students": total_students,
        "unique_checked_in": unique_checked_in,
        "remaining": remaining
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)