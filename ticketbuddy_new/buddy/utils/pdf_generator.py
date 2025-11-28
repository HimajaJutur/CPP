import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import boto3
from botocore.exceptions import ClientError
import qrcode
from PIL import Image

# ✅ your correct bucket name
BUCKET_NAME = "ticketbuddy-tickets-943886678149"

s3 = boto3.client("s3")

def generate_ticket_pdf(booking):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    # Colors
    BLUE = (0/255, 90/255, 255/255)
    DARK = (30/255, 30/255, 30/255)

    # === HEADER ===
    pdf.setFillColorRGB(*BLUE)
    pdf.rect(0, 780, 595, 60, fill=1)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(30, 808, "TICKETBUDDY BOARDING PASS")

    # === MAIN CARD ===
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setStrokeColorRGB(0.8, 0.8, 0.8)
    pdf.rect(30, 520, 535, 240, fill=0, stroke=1)

    # --- Booking ID ---
    pdf.setFont("Helvetica-Bold", 18)
    pdf.setFillColorRGB(*DARK)
    pdf.drawString(45, 735, f"Booking ID: {booking['booking_id']}")

    # --- Passenger ---
    pdf.setFont("Helvetica", 14)
    pdf.drawString(45, 710, f"Passenger: {booking['username']}")

    # --- Route ---
    pdf.setFont("Helvetica-Bold", 20)
    pdf.setFillColorRGB(*BLUE)
    pdf.drawString(45, 675, f"{booking['source']}  →  {booking['destination']}")

    # --- Date & Time ---
    pdf.setFillColorRGB(0.95, 0.95, 0.95)
    pdf.roundRect(40, 600, 250, 60, 10, fill=1)

    pdf.setFillColorRGB(*DARK)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 640, "Departure:")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 620, booking['departure_time'])

    pdf.setFont("Helvetica", 12)
    pdf.drawString(160, 640, "Arrival:")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(160, 620, booking['arrival_time'])

    # --- Fare ---
    pdf.setFont("Helvetica", 12)
    pdf.drawString(45, 580, "Total Fare:")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(45, 560, f"€{booking['fare']}")

    # --- Seats ---
    pdf.setFont("Helvetica", 12)
    pdf.drawString(200, 580, "Seats:")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, 560, ", ".join(booking.get("seats", [])))

    # ======== REAL QR CODE GENERATION ========

    qr_data = f"""
TicketBuddy Boarding Pass
Booking ID: {booking['booking_id']}
Passenger: {booking['username']}
From: {booking['source']}
To: {booking['destination']}
Departure: {booking['departure_time']}
Seats: {', '.join(booking.get('seats', []))}
    """

    qr_img = qrcode.make(qr_data)

    # Convert QR image → Bytes → PIL Image (ReportLab compatible)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pil_qr = Image.open(qr_buffer)

    # Draw QR code on PDF
    pdf.drawInlineImage(pil_qr, 450, 590, width=100, height=100)

    # QR title
    pdf.setFont("Helvetica", 10)
    pdf.drawString(460, 580, "SCAN TO VERIFY")

    # === FOOTER ===
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.4, 0.4, 0.4)
    pdf.drawString(30, 505, "Thank you for riding with TicketBuddy!")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer




def upload_ticket_pdf(buffer, filename):
    """Uploads PDF and returns a pre-signed URL (works in Learner Lab)"""
    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=filename,
            Body=buffer.getvalue(),
            ContentType='application/pdf'
        )

        # Generate 7-day downloadable URL
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": BUCKET_NAME, "Key": filename},
            ExpiresIn=7 * 24 * 3600   # 7 days
        )

        return url

    except ClientError as e:
        print("S3 Upload Error:", e)
        return None