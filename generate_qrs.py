import os
import qrcode

# Output folder for your QR PNG files
OUTPUT_DIR = "qr_codes"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Student IDs to turn into QR images
STUDENT_IDS = [
    "STU-001",
    "STU-002",
    "STU-003",
    "STU-004",
    "STU-005",
]

for student_id in STUDENT_IDS:
    # Build a crisp, easily scannable QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(student_id)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    file_path = os.path.join(OUTPUT_DIR, f"{student_id}.png")
    img.save(file_path)
    print(f"Saved: {file_path}")