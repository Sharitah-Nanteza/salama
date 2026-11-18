import os
from flask import Flask, render_template_string, request, jsonify
from dotenv import load_dotenv
import africastalking
from datetime import datetime

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
    }
}

SCANNER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Salama Gate Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- Include HTML5 QR Code Scanner Library -->
    <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; background: #f4f7f6; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); max-width: 450px; margin: auto; }
        input { width: 80%; padding: 12px; font-size: 18px; margin: 10px 0; border: 1px solid #ccc; border-radius: 6px; }
        button { background: #2e7d32; color: white; border: none; padding: 12px 25px; font-size: 18px; border-radius: 6px; cursor: pointer; }
        .result { margin-top: 20px; padding: 15px; border-radius: 6px; font-weight: bold; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
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
            <input type="text" id="student_id" name="student_id" placeholder="e.g. STU-001" autofocus required><br>
            <button type="submit">Verify & Notify</button>
        </form>

        {% if message %}
            <div class="result {{ status }}">{{ message }}</div>
        {% endif %}
    </div>

    <script>
        function startScanner() {
            document.getElementById('reader').style.display = 'block';
            document.getElementById('scan-btn').style.display = 'none';
            
            function onScanSuccess(decodedText, decodedResult) {
                // Automatically fill the input and submit the form when QR is scanned!
                document.getElementById('student_id').value = decodedText;
                document.getElementById('checkin-form').submit();
                html5QrCode.stop();
            }

            let html5QrCode = new Html5Qrcode("reader");
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

@app.route("/", methods=["GET"])
def index():
    return render_template_string(SCANNER_HTML)

@app.route("/scan", methods=["POST"])
def scan():
    student_id = request.form.get("student_id", "").strip()
    student = STUDENTS_DB.get(student_id)

    if not student:
        return render_template_string(SCANNER_HTML, message=f"Unrecognized ID: {student_id}", status="error")

    now = datetime.now().strftime("%I:%M %p")
    message = f"Salama Alert: Your child {student['name']} ({student['class']}) safely checked in at school at {now}."

    try:
        response = sms.send(message, [student["parent_phone"]])
        print("SMS Response:", response)
    except Exception as e:
        print("SMS Error:", e)

    success_msg = f"Checked In: {student['name']} ({student['class']}) at {now}. SMS sent to parent!"
    return render_template_string(SCANNER_HTML, message=success_msg, status="success")

if __name__ == "__main__":
    app.run(debug=True, port=5000)