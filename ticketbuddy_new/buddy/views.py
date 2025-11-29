from django.shortcuts import render, redirect
from django.contrib import messages
from .cognito_auth import cognito_signup, cognito_confirm, cognito_login
import boto3
from django.contrib import messages
import json
from .fares import FARES
from .schedules import SCHEDULES
from buddy.utils.pdf_generator import generate_ticket_pdf, upload_ticket_pdf

dynamo = boto3.resource("dynamodb")
tickets_table = dynamo.Table("TicketBuddy_Tickets")
seats_table = dynamo.Table("TicketBuddy_Seats")
sns = boto3.client("sns")

SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:943886678149:TicketBuddy_Alerts"

def send_booking_email(username, subject, message):
    """
    Sends ticket email using SNS. SNS will send plain text email.
    """
    full_message = f"Hello {username},\n\n{message}\n\n— TicketBuddy"
    
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=subject,
        Message=full_message
    )


lambda_client = boto3.client("lambda", region_name="us-east-1")


def lambda_handler(event, context):
    try:
        booking_id = event.get("booking_id")
        if not booking_id:
            return {"status": "error", "message": "Missing booking_id"}

        # 1️⃣ Fetch ticket
        resp = tickets_table.get_item(Key={"booking_id": booking_id})
        ticket = resp.get("Item")

        if not ticket:
            return {"status": "error", "message": "Booking not found"}

        route = ticket.get("route")
        dep_time = ticket.get("departure_time")
        seats = ticket.get("seats", [])
        username = ticket.get("username")
        pdf_url = ticket.get("pdf_url", "")
        source = ticket.get("source")
        destination = ticket.get("destination")
        date = ticket.get("departure_date")

        # 2️⃣ Release seats
        if route and dep_time and seats:
            for seat in seats:
                composite_key = f"{dep_time}#{seat}"

                seats_table.update_item(
                    Key={
                        "route_id": route,
                        "departure_time_seat": composite_key
                    },
                    UpdateExpression="SET #s = :a",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":a": "AVAILABLE"}
                )

        # 3️⃣ Mark ticket cancelled
        tickets_table.update_item(
            Key={"booking_id": booking_id},
            UpdateExpression="SET #s = :c",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":c": "CANCELLED"}
        )

        # 4️⃣ Send Cancellation Email
        message = (
            f"Your TicketBuddy booking has been CANCELLED.\n\n"
            f"Booking ID: {booking_id}\n"
            f"Route: {source} → {destination}\n"
            f"Date: {date}\n"
            f"Seats: {', '.join(seats)}\n"
            f"Status: CANCELLED\n\n"
            f"Ticket PDF (Cancelled Copy):\n{pdf_url}"
        )

        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject="TicketBuddy – Ticket Cancelled",
            Message=message
        )

        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


from .cognito_auth import (
    cognito_signup, cognito_confirm, cognito_login,
    cognito_forgot_password, cognito_confirm_new_password
)


def index(request):
    username = request.session.get("username")
    if not username:
        return redirect("login")

    return render(request, "buddy/index.html", {"username": username})


def register_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]

        res = cognito_signup(username, email, password)

        if "error" in res:
            messages.error(request, res["error"])
            return redirect("register")

        request.session["pending_username"] = username
        return redirect("confirm")

    return render(request, "buddy/register.html")


def confirm_view(request):
    if request.method == "POST":
        username = request.session.get("pending_username")
        code = request.POST["code"]

        res = cognito_confirm(username, code)

        if "error" in res:
            messages.error(request, res["error"])
            return redirect("confirm")

        messages.success(request, "Account confirmed! Login now.")
        return redirect("login")

    return render(request, "buddy/confirm.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        res = cognito_login(username, password)

        if "error" in res:
            messages.error(request, res["error"])
            return render(request, "buddy/login.html")  # <-- FIXED

        tokens = res["AuthenticationResult"]
        request.session["id_token"] = tokens["IdToken"]
        request.session["access_token"] = tokens["AccessToken"]
        request.session["username"] = username
        return redirect("index")

    return render(request, "buddy/login.html")


def logout_view(request):
    request.session.flush()
    return redirect("login")




def forgot_password_view(request):
    if request.method == "POST":
        username = request.POST["username"]

        res = cognito_forgot_password(username)
        if "error" in res:
            messages.error(request, res["error"])
            return redirect("forgot-password")

        request.session["reset_username"] = username
        messages.success(request, "OTP sent to your email.")
        return redirect("reset-password")

    return render(request, "buddy/forgot_password.html")


def reset_password_view(request):
    if request.method == "POST":
        username = request.session.get("reset_username")
        code = request.POST["code"]
        new_password = request.POST["password"]

        res = cognito_confirm_new_password(username, code, new_password)

        if "error" in res:
            messages.error(request, res["error"])
            return redirect("reset-password")

        messages.success(request, "Password reset successful! You can now login.")
        return redirect("login")

    return render(request, "buddy/reset_password.html")


lambda_client = boto3.client("lambda")


def dashboard(request):
    return render(request, "buddy/index.html")

def book_ticket_page(request):
    if request.method == "POST":

        # -----------------------------
        # (1) Read POST Data
        # -----------------------------
        seats_str = request.POST.get("selected_seats", "")
        selected_seats = [s for s in seats_str.split(",") if s]

        route = request.POST.get("route") or request.POST.get("route_id")

        ticket_type = request.POST.get("ticket_type")        # "One Way" / "Return"
        is_return = ticket_type == "Return"

        return_date = request.POST.get("return_date")        # return date
        departure_date = request.POST.get("departure_date")  # outbound date

        """     # -----------------------------
        # (2) Book outbound seats first
        # -----------------------------
        booking_id_for_seats = None

        if selected_seats and route:
            seat_payload = {
                "route_id": route,
                "departure_time": request.POST.get("departure_time"),
                "seats": selected_seats
            }

            seat_resp = lambda_client.invoke(
                FunctionName="TicketBuddy_UpdateSeat",
                InvocationType="RequestResponse",
                Payload=json.dumps(seat_payload)
            )

            seat_result = json.loads(seat_resp["Payload"].read())

            if seat_result.get("status") != "success":
                messages.error(request, f"Selected seats conflict: {seat_result.get('message')}")
                return redirect(
                    f"/book-ticket?route={route}&from={request.POST.get('from')}&to={request.POST.get('to')}"
                )

            booking_id_for_seats = seat_result.get("booking_id")
        """
        # -----------------------------
        # (3) Create Outbound Ticket
        # -----------------------------
        book_payload = {
            "username": request.session.get("username"),
            "from": request.POST.get("from"),
            "to": request.POST.get("to"),
            "passengers": request.POST.get("passengers"),
            "departure_date": departure_date,
            "return_date": return_date,
            "ticket_type": ticket_type,
            "seats": selected_seats,
            "fare": request.POST.get("fare"),
            "route": route,
            "departure_time": request.POST.get("departure_time"),
            "arrival_time": request.POST.get("arrival_time"),
        }
        
        # Save pending outbound booking in session
        request.session["pending_booking"] = book_payload
        request.session["pending_booking_ts"] = str(__import__("time").time())
        
        # If user selected Return, redirect to return-seat page to choose return seats
        if is_return:
            # pass params for return selection prefill (swap from/to)
            return redirect(
                f"/return-seat?from={book_payload['to']}"
                f"&to={book_payload['from']}"
                f"&date={book_payload['return_date']}"
                f"&fare={book_payload['fare']}"
                f"&route={book_payload['route']}"
                f"&departure_time={book_payload['departure_time']}"
                f"&arrival_time={book_payload['arrival_time']}"
            )
        
        # Otherwise One Way -> go directly to payment
        return redirect(
            f"/payment?from={book_payload['from']}&to={book_payload['to']}"
            f"&date={book_payload['departure_date']}&fare={book_payload['fare']}"
            f"&route={book_payload['route']}&departure_time={book_payload['departure_time']}"
            f"&arrival_time={book_payload['arrival_time']}"
        )
        
    
        """      
        if booking_id_for_seats:
            book_payload["booking_id"] = booking_id_for_seats

        resp = lambda_client.invoke(
            FunctionName="TicketBuddy_BookTicket",
            InvocationType="RequestResponse",
            Payload=json.dumps(book_payload)
        )

        result = json.loads(resp['Payload'].read())

        if result.get("status") != "success":
            messages.error(request, "Failed to book ticket.")
            return redirect("book-ticket")

        # booking created
        outbound_booking = result.get("item")
        outbound_id = outbound_booking["booking_id"]

        # -----------------------------
        # (4) Generate PDF for Outbound
        # -----------------------------
        pdf_buffer = generate_ticket_pdf(outbound_booking)
        filename = f"tickets/{outbound_id}.pdf"
        pdf_url = upload_ticket_pdf(pdf_buffer, filename)
        


        table = dynamo.Table("TicketBuddy_Tickets")
        table.update_item(
            Key={"booking_id": outbound_id},
            UpdateExpression="SET pdf_url = :p",
            ExpressionAttributeValues={":p": pdf_url},
        )
        
        
        # --- SEND BOOKING EMAIL ---
        email_subject = "Your TicketBuddy Ticket is Confirmed!"
        email_message = (
            f"Booking ID: {outbound_id}\n"
            f"Route: {outbound_booking['source']} → {outbound_booking['destination']}\n"
            f"Date: {departure_date}\n"
            f"Departure Time: {outbound_booking['departure_time']}\n"
            f"Seats: {', '.join(outbound_booking.get('seats', []))}\n"
            f"Fare: €{outbound_booking['fare']}\n\n"
            f"Download Your Ticket:\n{pdf_url}"
        )
        
        send_booking_email(
            outbound_booking["username"],
            email_subject,
            email_message
        )


        # -----------------------------
        # (5) If Return Ticket → Redirect
        # -----------------------------
        if is_return:
            return redirect(
                f"/return-seat"
                f"?from={book_payload['to']}"
                f"&to={book_payload['from']}"
                f"&date={return_date}"
                f"&fare={book_payload['fare']}"
                f"&route={route}"
                f"&departure_time={book_payload['departure_time']}"
                f"&arrival_time={book_payload['arrival_time']}"
                f"&outbound_id={outbound_id}"
            )


        # -----------------------------
        # (6) Finish normal outbound booking
        # -----------------------------
        messages.success(request, "Ticket booked successfully!")
        return redirect("/history")
        """
    # -----------------------------------------------------------------
    # GET → show booking page
    # -----------------------------------------------------------------
    prefill = {
        "from": request.GET.get("from", ""),
        "to": request.GET.get("to", ""),
        "route": request.GET.get("route", ""),
        "fare": request.GET.get("fare", ""),
        "departure_time": request.GET.get("time", ""),
        "arrival_time": request.GET.get("arrival", ""),
        "date": request.GET.get("date", ""),
        "return_date": request.GET.get("return_date", ""),
    }

    # -----------------------------
    # Get booked seats for this route
    # -----------------------------
    booked = []
    if prefill.get("route"):
        try:
            seat_resp = lambda_client.invoke(
                FunctionName="TicketBuddy_GetSeatStatus",
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "route_id": prefill["route"],
                    "departure_time": prefill["departure_time"]
                })
            )
            seat_result = json.loads(seat_resp["Payload"].read())

            if seat_result.get("status") == "success":
                booked = seat_result.get("booked_seats", [])

        except Exception:
            booked = []

    return render(request, "buddy/booking.html", {"prefill": prefill, "booked": booked})

def payment_page(request):
    """
    Payment selection UI.
    Shows payment.html using the pending booking stored in session (preferred).
    Falls back to GET params if session missing.
    """
    # Attempt to fetch pending booking from session

    pending_out = request.session.get("pending_booking")
    pending_ret = request.session.get("pending_return_booking")
    
    context = {
        "from": "",
        "to": "",
        "date": "",
        "fare": 0,
        "seats": "",
        "route": "",
        "departure_time": "",
        "arrival_time": "",
        "ticket_type": "",
        "outbound_fare": 0,
        "return_fare": 0,
        "total_fare": 0,
        "outbound_seats": "",
        "return_seats": "",
        "outbound_route": "",
        "return_route": "",
        "outbound_departure_time": "",
        "return_departure_time": "",
        "outbound_arrival_time": "",
        "return_arrival_time": "",
    }
    """
    context = {}
    if pending:
        context["from"] = pending.get("from")
        context["to"] = pending.get("to")
        context["date"] = pending.get("departure_date")
        context["fare"] = pending.get("fare")
        context["seats"] = ", ".join(pending.get("seats", []))
        context["route"] = pending.get("route")
        context["departure_time"] = pending.get("departure_time")
        context["arrival_time"] = pending.get("arrival_time")
        context["ticket_type"] = pending.get("ticket_type")
        context["outbound_id"] = pending.get("booking_id", "")
        context["parent_booking_id"] = pending.get("parent_booking_id", "")
        context["return_date"] = pending.get("return_date", "")
    else:
        # fallback to GET params (if user arrived with query string)
        context["from"] = request.GET.get("from", "")
        context["to"] = request.GET.get("to", "")
        context["date"] = request.GET.get("date", "")
        context["fare"] = request.GET.get("fare", "")
        context["seats"] = request.GET.get("seats", "")
        context["route"] = request.GET.get("route", "")
        context["departure_time"] = request.GET.get("departure_time", "")
        context["arrival_time"] = request.GET.get("arrival_time", "")
        context["ticket_type"] = request.GET.get("ticket_type", "")
        context["outbound_id"] = request.GET.get("outbound_id", "")
        context["parent_booking_id"] = request.GET.get("parent_booking_id", "")
        context["return_date"] = request.GET.get("return_date", "")
    """
    
    if pending_out:
        context["from"] = pending_out.get("from")
        context["to"] = pending_out.get("to")
        context["date"] = pending_out.get("departure_date")
        context["outbound_fare"] = float(pending_out.get("fare") or 0)
        context["outbound_seats"] = ", ".join(pending_out.get("seats", []))
        context["outbound_route"] = pending_out.get("route")
        context["outbound_departure_time"] = pending_out.get("departure_time")
        context["outbound_arrival_time"] = pending_out.get("arrival_time")
        context["ticket_type"] = pending_out.get("ticket_type")
        context["fare"] = context["outbound_fare"]

    # If we have a pending return booking, include it
    if pending_ret:
        context["return_fare"] = float(pending_ret.get("fare") or 0)
        context["return_seats"] = ", ".join(pending_ret.get("seats", []))
        context["return_route"] = pending_ret.get("route")
        context["return_departure_time"] = pending_ret.get("departure_time")
        context["return_arrival_time"] = pending_ret.get("arrival_time")

    context["total_fare"] = context["outbound_fare"] + context["return_fare"]
    return render(request, "buddy/payment.html", context)

"""
def payment_success(request):
   
    
    pending_out = request.session.get("pending_booking")
    pending_ret = request.session.get("pending_return_booking")
    # Use session pending booking primarily
    pending = request.session.get("pending_booking")

    # If session missing, try GET params (graceful fallback)
    if not pending:
        pending = {
            "username": request.session.get("username"),
            "from": request.GET.get("from"),
            "to": request.GET.get("to"),
            "passengers": request.GET.get("passengers") or 1,
            "departure_date": request.GET.get("date"),
            "return_date": request.GET.get("return_date"),
            "ticket_type": request.GET.get("ticket_type") or "One Way",
            "seats": [s for s in (request.GET.get("seats") or "").split(",") if s],
            "fare": request.GET.get("fare"),
            "route": request.GET.get("route"),
            "departure_time": request.GET.get("departure_time"),
            "arrival_time": request.GET.get("arrival_time"),
            #"parent_booking_id": request.GET.get("parent_booking_id"),
        }
    
    # -----------------------------
    # Validate required fields
    # -----------------------------
    seats = pending.get("seats", [])
    route = pending.get("route")
    username = pending.get("username") or request.session.get("username")

    if not route or not seats:
        messages.error(request, "Missing route or seats — cannot complete payment.")
        return redirect("book-ticket")
        
    # Fallback for return
    if not pending_ret and request.GET.get("return_seats"):
        pending_ret = {
            "username": request.session.get("username"),
            "from": request.GET.get("ret_from"),
            "to": request.GET.get("ret_to"),
            "passengers": int(request.GET.get("ret_passengers") or 1),
            "departure_date": request.GET.get("ret_date"),
            "ticket_type": "Return",
            "seats": [s for s in (request.GET.get("return_seats") or "").split(",") if s],
            "fare": float(request.GET.get("ret_fare") or 0),
            "route": request.GET.get("ret_route"),
            "departure_time": request.GET.get("ret_departure_time"),
            "arrival_time": request.GET.get("ret_arrival_time"),
        }
    
    # Basic sanity
    outbound_seats = pending_out.get("seats", [])
    outbound_route = pending_out.get("route")
    username = pending_out.get("username") or request.session.get("username")
    """
"""
    # sanity checks
    seats = pending.get("seats", [])
    route = pending.get("route")
    username = pending.get("username") or request.session.get("username")
    
    if not route or not seats:
        messages.error(request, "Missing route or seats — cannot complete payment.")
        return redirect("book-ticket")
    """
"""
    if not outbound_route or not outbound_seats:
        messages.error(request, "Missing outbound route or seats — cannot complete payment.")
        return redirect("book-ticket")
    """
"""
    # -----------------------------
    # (1) Update seats via Lambda (lock seats)
    # -----------------------------
    try:
        seat_payload = {
            "route_id": route,
            "departure_time": pending.get("departure_time"),
            "seats": seats
        }

        seat_resp = lambda_client.invoke(
            FunctionName="TicketBuddy_UpdateSeat",
            InvocationType="RequestResponse",
            Payload=json.dumps(seat_payload)
        )
        seat_result = json.loads(seat_resp["Payload"].read())

        if seat_result.get("status") != "success":
            messages.error(request, f"Selected seats conflict: {seat_result.get('message')}")
            # cleanup pending booking from session
            request.session.pop("pending_booking", None)
            return redirect(
                f"/book-ticket?route={route}&from={pending.get('from')}&to={pending.get('to')}"
            )

        # If update seat returns an assigned booking_id for seats, use it
        booking_id_for_seats = seat_result.get("booking_id")
    except Exception as e:
        messages.error(request, "Failed to lock seats. Try again.")
        request.session.pop("pending_booking", None)
        return redirect("book-ticket")
    """
"""
    
    # -----------------------------
    # (A) Lock outbound seats
    # -----------------------------
    try:
        seat_payload_out = {
            "route_id": outbound_route,
            "departure_time": pending_out.get("departure_time"),
            "seats": outbound_seats
        }

        seat_resp = lambda_client.invoke(
            FunctionName="TicketBuddy_UpdateSeat",
            InvocationType="RequestResponse",
            Payload=json.dumps(seat_payload_out)
        )
        seat_result = json.loads(seat_resp["Payload"].read())

        if seat_result.get("status") != "success":
            messages.error(request, f"Selected outbound seats conflict: {seat_result.get('message')}")
            # cleanup pending booking from session
            request.session.pop("pending_booking", None)
            request.session.pop("pending_return_booking", None)
            return redirect(
                f"/book-ticket?route={outbound_route}&from={pending_out.get('from')}&to={pending_out.get('to')}"
            )

        booking_id_for_seats_out = seat_result.get("booking_id")
    except Exception:
        messages.error(request, "Failed to lock outbound seats. Try again.")
        request.session.pop("pending_booking", None)
        request.session.pop("pending_return_booking", None)
        return redirect("book-ticket")
    # -----------------------------
    # (2) Book ticket via Lambda
    # -----------------------------
    book_payload = {
        "username": username,
        "from": pending.get("from"),
        "to": pending.get("to"),
        "passengers": pending.get("passengers"),
        "departure_date": pending.get("departure_date"),
        "return_date": pending.get("return_date"),
        "ticket_type": pending.get("ticket_type"),
        "seats": seats,
        "fare": pending.get("fare"),
        "route": route,
        "departure_time": pending.get("departure_time"),
        "arrival_time": pending.get("arrival_time"),
    }
    """
"""
    # if seat locking returned a booking_id, include it
    if booking_id_for_seats:
        book_payload["booking_id"] = booking_id_for_seats

    # If there's a parent_booking_id (return ticket flow), include it
    if pending.get("parent_booking_id"):
        book_payload["parent_booking_id"] = pending.get("parent_booking_id")

    try:
        resp = lambda_client.invoke(
            FunctionName="TicketBuddy_BookTicket",
            InvocationType="RequestResponse",
            Payload=json.dumps(book_payload)
        )
        result = json.loads(resp['Payload'].read())

        if result.get("status") != "success":
            messages.error(request, "Failed to book ticket after payment.")
            request.session.pop("pending_booking", None)
            return redirect("book-ticket")
    except Exception as e:
        messages.error(request, "Failed to create booking. Try again.")
        request.session.pop("pending_booking", None)
        return redirect("book-ticket")

    # booking created
    booking_item = result.get("item")
    booking_id = booking_item["booking_id"]
    """
""""
    if booking_id_for_seats_out:
        book_payload_out["booking_id"] = booking_id_for_seats_out

    try:
        resp = lambda_client.invoke(
            FunctionName="TicketBuddy_BookTicket",
            InvocationType="RequestResponse",
            Payload=json.dumps(book_payload_out)
        )
        result = json.loads(resp['Payload'].read())

        if result.get("status") != "success":
            messages.error(request, "Failed to book outbound ticket after payment.")
            request.session.pop("pending_booking", None)
            request.session.pop("pending_return_booking", None)
            return redirect("book-ticket")
    except Exception:
        messages.error(request, "Failed to create outbound booking. Try again.")
        request.session.pop("pending_booking", None)
        request.session.pop("pending_return_booking", None)
        return redirect("book-ticket")
    """
"""
    # outbound created
    outbound_item = result.get("item")
    outbound_id = outbound_item["booking_id"]
    """
    # -----------------------------
    # (3) Generate PDF for booking
    # -----------------------------
"""
    try:
        pdf_buffer = generate_ticket_pdf(booking_item)
        filename = f"tickets/{booking_id}.pdf"
        pdf_url = upload_ticket_pdf(pdf_buffer, filename)

        # update ticket item with pdf_url
        tickets_table.update_item(
            Key={"booking_id": booking_id},
            UpdateExpression="SET pdf_url = :p",
            ExpressionAttributeValues={":p": pdf_url},
        )
    except Exception as e:
        # PDF generation/upload failed — but booking exists. Notify user and continue.
        pdf_url = ""
        # you may want to log e

    # --- SEND BOOKING EMAIL ---
    try:
        email_subject = "Your TicketBuddy Ticket is Confirmed!"
        email_message = (
            f"Booking ID: {booking_id}\n"
            f"Route: {booking_item.get('source','')} → {booking_item.get('destination','')}\n"
            f"Date: {booking_item.get('departure_date')}\n"
            f"Departure Time: {booking_item.get('departure_time')}\n"
            f"Seats: {', '.join(booking_item.get('seats', []))}\n"
            f"Fare: €{booking_item.get('fare')}\n\n"
            f"Download Your Ticket:\n{pdf_url}"
        )

        send_booking_email(
            booking_item.get("username", username),
            email_subject,
            email_message
        )
    except Exception:
        pass

    # clear pending booking from session
    request.session.pop("pending_booking", None)
    request.session.pop("pending_booking_ts", None)

    messages.success(request, "Payment received and ticket booked successfully!")
    return redirect("history")
    """
    
    # -----------------------------
    # (C) Generate PDF for outbound
    # -----------------------------
"""
    try:
        pdf_buffer_out = generate_ticket_pdf(outbound_item)
        filename_out = f"tickets/{outbound_id}.pdf"
        pdf_url_out = upload_ticket_pdf(pdf_buffer_out, filename_out)

        tickets_table.update_item(
            Key={"booking_id": outbound_id},
            UpdateExpression="SET pdf_url = :p",
            ExpressionAttributeValues={":p": pdf_url_out},
        )
    except Exception:
        pdf_url_out = ""

    # Send outbound email
    try:
        email_subject_out = "Your TicketBuddy Ticket is Confirmed!"
        email_message_out = (
            f"Booking ID: {outbound_id}\n"
            f"Route: {outbound_item.get('source','')} → {outbound_item.get('destination','')}\n"
            f"Date: {outbound_item.get('departure_date')}\n"
            f"Departure Time: {outbound_item.get('departure_time')}\n"
            f"Seats: {', '.join(outbound_item.get('seats', []))}\n"
            f"Fare: €{outbound_item.get('fare')}\n\n"
            f"Download Your Ticket:\n{pdf_url_out}"
        )
        send_booking_email(outbound_item.get("username", username), email_subject_out, email_message_out)
    except Exception:
        pass

    # -----------------------------
    # (D) If return present -> lock seats and book return with parent_booking_id
    # -----------------------------
    if pending_ret:
        return_seats = pending_ret.get("seats", [])
        return_route = pending_ret.get("route")

        if not return_route or not return_seats:
            # can't proceed with return -> clear and finish outbound only
            messages.warning(request, "Return booking missing seats or route. Outbound booked.")
            request.session.pop("pending_booking", None)
            request.session.pop("pending_return_booking", None)
            return redirect("history")

        # lock return seats
        try:
            seat_payload_ret = {
                "route_id": return_route,
                "departure_time": pending_ret.get("departure_time"),
                "seats": return_seats
            }

            seat_resp_ret = lambda_client.invoke(
                FunctionName="TicketBuddy_UpdateSeat",
                InvocationType="RequestResponse",
                Payload=json.dumps(seat_payload_ret)
            )
            seat_result_ret = json.loads(seat_resp_ret["Payload"].read())

            if seat_result_ret.get("status") != "success":
                messages.error(request, f"Selected return seats conflict: {seat_result_ret.get('message')}")
                # We already booked outbound. Consider alerting or issuing a refund process.
                request.session.pop("pending_booking", None)
                request.session.pop("pending_return_booking", None)
                return redirect("history")

            booking_id_for_seats_ret = seat_result_ret.get("booking_id")
        except Exception:
            messages.error(request, "Failed to lock return seats. Outbound booked.")
            request.session.pop("pending_booking", None)
            request.session.pop("pending_return_booking", None)
            return redirect("history")

        # book return ticket with parent_booking_id set to outbound_id
        book_payload_ret = {
            "username": username,
            "from": pending_ret.get("from"),
            "to": pending_ret.get("to"),
            "passengers": pending_ret.get("passengers"),
            "departure_date": pending_ret.get("departure_date"),
            "ticket_type": "Return",
            "seats": return_seats,
            "fare": pending_ret.get("fare"),
            "route": return_route,
            "departure_time": pending_ret.get("departure_time"),
            "arrival_time": pending_ret.get("arrival_time"),
            "parent_booking_id": outbound_id
        }

        if booking_id_for_seats_ret:
            book_payload_ret["booking_id"] = booking_id_for_seats_ret

        try:
            resp_ret = lambda_client.invoke(
                FunctionName="TicketBuddy_BookTicket",
                InvocationType="RequestResponse",
                Payload=json.dumps(book_payload_ret)
            )
            result_ret = json.loads(resp_ret['Payload'].read())

            if result_ret.get("status") != "success":
                messages.error(request, "Failed to book return ticket after payment. Outbound booked.")
                request.session.pop("pending_booking", None)
                request.session.pop("pending_return_booking", None)
                return redirect("history")
        except Exception:
            messages.error(request, "Failed to create return booking. Outbound booked.")
            request.session.pop("pending_booking", None)
            request.session.pop("pending_return_booking", None)
            return redirect("history")

        # return booked
        return_item = result_ret.get("item")
        return_id = return_item["booking_id"]

        # generate return PDF
        try:
            pdf_buffer_ret = generate_ticket_pdf(return_item)
            filename_ret = f"tickets/{return_id}.pdf"
            pdf_url_ret = upload_ticket_pdf(pdf_buffer_ret, filename_ret)

            tickets_table.update_item(
                Key={"booking_id": return_id},
                UpdateExpression="SET pdf_url = :p",
                ExpressionAttributeValues={":p": pdf_url_ret},
            )
        except Exception:
            pdf_url_ret = ""

        # send return email
        try:
            email_subject_ret = "Your TicketBuddy RETURN Ticket is Confirmed!"
            email_message_ret = (
                f"Return Ticket ID: {return_id}\n"
                f"Outbound Ticket: {outbound_id}\n\n"
                f"Route: {return_item.get('source','')} → {return_item.get('destination','')}\n"
                f"Return Date: {return_item.get('departure_date')}\n"
                f"Departure Time: {return_item.get('departure_time')}\n"
                f"Seats: {', '.join(return_item.get('seats', []))}\n"
                f"Fare: €{return_item.get('fare')}\n\n"
                f"Download Your Return Ticket:\n{pdf_url_ret}"
            )
            send_booking_email(return_item.get("username", username), email_subject_ret, email_message_ret)
        except Exception:
            pass

    # clear pending sessions
    request.session.pop("pending_booking", None)
    request.session.pop("pending_return_booking", None)
    request.session.pop("pending_booking_ts", None)

    messages.success(request, "Payment received and ticket(s) booked successfully!")
    return redirect("history")
"""
def history_page(request):
    username = request.session.get("username")

    # get bookings via Lambda
    response = lambda_client.invoke(
        FunctionName="TicketBuddy_GetHistory",
        InvocationType="RequestResponse",
        Payload=json.dumps({"username": username})
    )
    result = json.loads(response['Payload'].read())
    bookings = result.get("bookings", []) if result.get("status") == "success" else []

    # ---------------------------
    # Convert dates to sortable form
    # ---------------------------
    from datetime import datetime

    def parse_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except:
            return datetime.min

    # ---------------------------
    # Group: outbound + return
    # ---------------------------
    grouped = {}

    for b in bookings:
        parent_id = b.get("parent_booking_id")

        if parent_id:
            # this is return ticket → attach to parent
            grouped.setdefault(parent_id, {"outbound": None, "returns": []})
            grouped[parent_id]["returns"].append(b)
        else:
            # this is outbound ticket
            grouped.setdefault(b["booking_id"], {"outbound": b, "returns": []})

    # ---------------------------
    # Convert grouped data into sorted list
    # ---------------------------
    final_list = []

    for parent_id, data in grouped.items():
        outbound = data["outbound"]
        returns = data["returns"]

        if outbound:
            final_list.append({
                "outbound": outbound,
                "returns": sorted(
                    returns,
                    key=lambda x: parse_date(x.get("departure_date", ""))  # sort return by date
                )
            })

    # sort all outbound groups by outbound date DESC
    final_list = sorted(
        final_list,
        key=lambda x: parse_date(x["outbound"].get("departure_date", "")),
        reverse=True
    )

    return render(request, "buddy/history.html", {"groups": final_list})


def payment_success(request):
    """
    Handles payment confirmation:
    - Lock outbound seats
    - Book outbound
    - If return exists: lock return seats + book return
    - Generate PDFs
    - Send emails
    """

    pending_out = request.session.get("pending_booking")
    pending_ret = request.session.get("pending_return_booking")

    if not pending_out:
        messages.error(request, "Session expired. Please book again.")
        return redirect("book-ticket")

    # -----------------------------
    # Extract outbound details
    # -----------------------------
    username = pending_out.get("username") or request.session.get("username")
    outbound_route = pending_out.get("route")
    outbound_seats = pending_out.get("seats", [])

    if not outbound_route or not outbound_seats:
        messages.error(request, "Missing outbound route or seats.")
        return redirect("book-ticket")

    # -----------------------------
    # (A) Lock outbound seats
    # -----------------------------
    try:
        seat_payload_out = {
            "route_id": outbound_route,
            "departure_time": pending_out.get("departure_time"),
            "seats": outbound_seats
        }

        seat_resp = lambda_client.invoke(
            FunctionName="TicketBuddy_UpdateSeat",
            InvocationType="RequestResponse",
            Payload=json.dumps(seat_payload_out)
        )
        seat_result = json.loads(seat_resp["Payload"].read())

        if seat_result.get("status") != "success":
            messages.error(request, seat_result.get("message"))
            return redirect("book-ticket")

        outbound_seat_booking_id = seat_result.get("booking_id")

    except Exception:
        messages.error(request, "Failed to lock outbound seats.")
        return redirect("book-ticket")

    # -----------------------------
    # (B) Book outbound ticket
    # -----------------------------
    book_payload_out = {
        "username": username,
        "from": pending_out.get("from"),
        "to": pending_out.get("to"),
        "passengers": pending_out.get("passengers"),
        "departure_date": pending_out.get("departure_date"),
        "ticket_type": pending_out.get("ticket_type"),
        "seats": outbound_seats,
        "fare": pending_out.get("fare"),
        "route": outbound_route,
        "departure_time": pending_out.get("departure_time"),
        "arrival_time": pending_out.get("arrival_time"),
    }

    if outbound_seat_booking_id:
        book_payload_out["booking_id"] = outbound_seat_booking_id

    try:
        resp = lambda_client.invoke(
            FunctionName="TicketBuddy_BookTicket",
            InvocationType="RequestResponse",
            Payload=json.dumps(book_payload_out)
        )
        result = json.loads(resp["Payload"].read())

        if result.get("status") != "success":
            messages.error(request, "Failed to book outbound ticket.")
            return redirect("book-ticket")

    except Exception:
        messages.error(request, "Outbound booking failed.")
        return redirect("book-ticket")

    outbound_item = result["item"]
    outbound_id = outbound_item["booking_id"]

    # -----------------------------
    # (C) Generate outbound PDF
    # -----------------------------
    try:
        pdf_buffer = generate_ticket_pdf(outbound_item)
        filename = f"tickets/{outbound_id}.pdf"
        pdf_url = upload_ticket_pdf(pdf_buffer, filename)

        tickets_table.update_item(
            Key={"booking_id": outbound_id},
            UpdateExpression="SET pdf_url = :p",
            ExpressionAttributeValues={":p": pdf_url},
        )
    except Exception:
        pdf_url = ""

    # Send outbound email
    try:
        send_booking_email(
            username,
            "Your TicketBuddy Ticket is Confirmed!",
            f"Booking ID: {outbound_id}\n"
            f"Route: {outbound_item.get('source')} → {outbound_item.get('destination')}\n"
            f"Date: {outbound_item.get('departure_date')}\n"
            f"Seats: {', '.join(outbound_seats)}\n"
            f"Fare: €{outbound_item.get('fare')}\n\n{pdf_url}"
        )
    except:
        pass

    # -----------------------------
    # (D) Handle RETURN booking if exists
    # -----------------------------
    if pending_ret:
        return_seats = pending_ret.get("seats", [])
        return_route = pending_ret.get("route")

        if return_route and return_seats:
            try:
                seat_payload_ret = {
                    "route_id": return_route,
                    "departure_time": pending_ret.get("departure_time"),
                    "seats": return_seats
                }

                seat_resp_ret = lambda_client.invoke(
                    FunctionName="TicketBuddy_UpdateSeat",
                    InvocationType="RequestResponse",
                    Payload=json.dumps(seat_payload_ret)
                )
                seat_result_ret = json.loads(seat_resp_ret["Payload"].read())

                if seat_result_ret.get("status") != "success":
                    messages.error(request, seat_result_ret.get("message"))
                    return redirect("history")

                return_seat_booking_id = seat_result_ret.get("booking_id")

            except:
                messages.error(request, "Failed to lock return seats.")
                return redirect("history")

            # Book return ticket
            book_payload_ret = {
                "username": username,
                "from": pending_ret.get("from"),
                "to": pending_ret.get("to"),
                "passengers": pending_ret.get("passengers"),
                "departure_date": pending_ret.get("departure_date"),
                "ticket_type": "Return",
                "seats": return_seats,
                "fare": pending_ret.get("fare"),
                "route": return_route,
                "departure_time": pending_ret.get("departure_time"),
                "arrival_time": pending_ret.get("arrival_time"),
                "parent_booking_id": outbound_id
            }

            if return_seat_booking_id:
                book_payload_ret["booking_id"] = return_seat_booking_id

            try:
                resp_ret = lambda_client.invoke(
                    FunctionName="TicketBuddy_BookTicket",
                    InvocationType="RequestResponse",
                    Payload=json.dumps(book_payload_ret)
                )
                result_ret = json.loads(resp_ret["Payload"].read())
            except:
                result_ret = {}

            if result_ret.get("status") == "success":
                return_item = result_ret["item"]
                return_id = return_item["booking_id"]

                # PDF
                try:
                    pdf_buffer_ret = generate_ticket_pdf(return_item)
                    filename_ret = f"tickets/{return_id}.pdf"
                    pdf_url_ret = upload_ticket_pdf(pdf_buffer_ret, filename_ret)

                    tickets_table.update_item(
                        Key={"booking_id": return_id},
                        UpdateExpression="SET pdf_url = :p",
                        ExpressionAttributeValues={":p": pdf_url_ret},
                    )
                except:
                    pdf_url_ret = ""

                # Email
                try:
                    send_booking_email(
                        username,
                        "Your RETURN Ticket is Confirmed!",
                        f"Return ID: {return_id}\nOutbound: {outbound_id}\n\n"
                        f"{pdf_url_ret}"
                    )
                except:
                    pass

    # Clear session
    request.session.pop("pending_booking", None)
    request.session.pop("pending_return_booking", None)

    messages.success(request, "Payment complete! Ticket(s) booked successfully.")
    return redirect("history")





def alerts_page(request):
    return render(request, "buddy/alerts.html")

def profile_view(request):
    return render(request, "buddy/profile.html")
    
def cancel_ticket(request, booking_id):
    data = {"booking_id": booking_id}

    response = lambda_client.invoke(
        FunctionName="TicketBuddy_CancelTicket",
        InvocationType="RequestResponse",
        Payload=json.dumps(data)
    )

    result = json.loads(response["Payload"].read())

    if result.get("status") == "success":
        messages.success(request, "Ticket cancelled successfully!")
    else:
        messages.error(request, "Failed to cancel ticket.")

    return redirect("history")



def schedules_page(request):
    schedules = []
    date = request.GET.get("date", "")
    return_date = ""

    if request.method == "POST":
        source = request.POST.get("from")
        destination = request.POST.get("to")
        date = request.POST.get("date") 
        

        payload = {
            "from": source,
            "to": destination
        }

        response = lambda_client.invoke(
            FunctionName="TicketBuddy_GetSchedules",
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )

        result = json.loads(response['Payload'].read())

        # Lambda returns array directly inside body
        schedules = json.loads(result.get("body", "[]"))

    return render(request, "buddy/schedules.html", {"schedules": schedules,"date": date,"return_date": return_date})



def select_seat_page(request):
    route_id = request.GET.get("route")

    # Call Lambda to fetch seats
    payload = {"route_id": route_id}

    response = lambda_client.invoke(
        FunctionName="TicketBuddy_GetSeats",
        InvocationType="RequestResponse",
        Payload=json.dumps(payload)
    )

    result = json.loads(response["Payload"].read())

    seats = result.get("seats", [])

    return render(request, "buddy/select_seat.html", {
        "route_id": route_id,
        "seats": seats
    })
    
    
def destinations_page(request):
    # Call Lambda without any filters → fetch ALL routes
    payload = {}

    response = lambda_client.invoke(
        FunctionName="TicketBuddy_GetSchedules",
        InvocationType="RequestResponse",
        Payload=json.dumps(payload)
    )

    result = json.loads(response["Payload"].read())

    # Lambda returns { statusCode, body }
    schedules = json.loads(result.get("body", "[]"))

    return render(request, "buddy/destinations.html", {"schedules": schedules})


def contact_page(request):
    return render(request, "buddy/contact.html")
"""   
def return_seat_page(request):

    # -----------------------------------
    # POST → book the return ticket
    # -----------------------------------
    if request.method == "POST":

        seats_str = request.POST.get("selected_seats", "")
        seats = [s for s in seats_str.split(",") if s]

        route = request.POST.get("route")
        fare = request.POST.get("fare" or 0)
        return_date = request.POST.get("return_date")
        outbound_id = request.POST.get("outbound_id")

        username = request.session.get("username")

        # 1) UPDATE SEATS FIRST
        seat_payload = {
            "route_id": route,
            "departure_time": request.POST.get("departure_time"),
            "seats": seats
        }

        seat_resp = lambda_client.invoke(
            FunctionName="TicketBuddy_UpdateSeat",
            InvocationType="RequestResponse",
            Payload=json.dumps(seat_payload)
        )

        seat_result = json.loads(seat_resp["Payload"].read())
        if seat_result.get("status") != "success":
            messages.error(request, seat_result.get("message"))
            return redirect(request.path + "?" + request.META["QUERY_STRING"])

        # 2) BOOK RETURN TICKET
        book_payload = {
            "username": username,
            "from": request.POST.get("from"),
            "to": request.POST.get("to"),
            "passengers": len(seats),
            "departure_date": return_date,                 # <-- IMPORTANT
            "ticket_type": "Return",
            "seats": seats,
            "fare": fare,
            "route": route,
            "departure_time": request.POST.get("departure_time"),
            "arrival_time": request.POST.get("arrival_time"),

            "parent_booking_id": outbound_id              # <-- LINK TO OUTBOUND
        }

        book_resp = lambda_client.invoke(
            FunctionName="TicketBuddy_BookTicket",
            InvocationType="RequestResponse",
            Payload=json.dumps(book_payload)
        )

        book_result = json.loads(book_resp["Payload"].read())

        if book_result.get("status") != "success":
            messages.error(request, "Return ticket creation failed.")
            return redirect("/history")

        return_booking = book_result.get("item")
        return_id = return_booking["booking_id"]

        # 3) GENERATE PDF
        pdf_buffer = generate_ticket_pdf(return_booking)
        filename = f"tickets/{return_id}.pdf"
        pdf_url = upload_ticket_pdf(pdf_buffer, filename)


        
        dynamo.Table("TicketBuddy_Tickets").update_item(
            Key={"booking_id": return_id},
            UpdateExpression="SET pdf_url = :p",
            ExpressionAttributeValues={":p": pdf_url},
        )

        messages.success(request, "Return ticket booked!")
        return redirect("/history")
        
        # --- SEND RETURN TICKET EMAIL ---
        email_subject = "Your TicketBuddy RETURN Ticket is Confirmed!"
        email_message = (
            f"Return Ticket ID: {return_id}\n"
            f"Outbound Ticket: {outbound_id}\n\n"
            f"Route: {return_booking['source']} → {return_booking['destination']}\n"
            f"Return Date: {return_date}\n"
            f"Departure Time: {return_booking['departure_time']}\n"
            f"Seats: {', '.join(return_booking.get('seats', []))}\n"
            f"Fare: €{return_booking['fare']}\n\n"
            f"Download Your Return Ticket:\n{pdf_url}"
        )
        
        send_booking_email(
            return_booking["username"],
            email_subject,
            email_message
        )


    # -----------------------------------
    # GET → Seat selection page
    # -----------------------------------
    prefill = {
        "from": request.GET.get("from", ""),
        "to": request.GET.get("to", ""),
        "fare": request.GET.get("fare", ""),
        "route": request.GET.get("route", ""),
        "departure_time": request.GET.get("departure_time", ""),
        "arrival_time": request.GET.get("arrival_time", ""),
        "return_date": request.GET.get("date", ""),        # FIXED
        "outbound_id": request.GET.get("outbound_id", ""),
    }

    # Fetch already booked seats
    booked = []
    if prefill["route"]:
        try:
            seat_resp = lambda_client.invoke(
                FunctionName="TicketBuddy_GetSeatStatus",
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "route_id": prefill["route"],
                    "departure_time": prefill["departure_time"]
                })
            )
            seat_result = json.loads(seat_resp["Payload"].read())
            booked = seat_result.get("booked_seats", [])
        except:
            booked = []

    return render(request, "buddy/return_seat.html", {
        "prefill": prefill,
        "booked": booked
    })
"""

def return_seat_page(request):
    """
    If user POSTs here (after outbound), we WILL NOT book immediately.
    Instead we save a pending_return_booking in session and redirect to payment.
    """

    # -----------------------------------
    # POST → save pending return booking and redirect to payment
    # -----------------------------------
    if request.method == "POST":
        seats_str = request.POST.get("selected_seats", "")
        seats = [s for s in seats_str.split(",") if s]

        route = request.POST.get("route")
        fare = float(request.POST.get("fare") or 0)
        return_date = request.POST.get("return_date")
        outbound_id = request.POST.get("outbound_id")  # may be empty because outbound not booked yet

        username = request.session.get("username")

        # Build pending return payload (do NOT lock/book here)
        return_payload = {
            "username": username,
            "from": request.POST.get("from"),
            "to": request.POST.get("to"),
            "passengers": int(request.POST.get("passengers") or len(seats) or 1),
            "departure_date": return_date,
            "ticket_type": "Return",
            "seats": seats,
            "fare": fare,
            "route": route,
            "departure_time": request.POST.get("departure_time"),
            "arrival_time": request.POST.get("arrival_time"),
            # outbound linkage will be applied during payment_success using outbound id
            "parent_outbound_temp": outbound_id or ""
        }

        # Save pending return in session
        request.session["pending_return_booking"] = return_payload
        request.session["pending_return_booking_ts"] = str(__import__("time").time())

        # Redirect to payment where both fares will be shown
        return redirect("/payment")

    # -----------------------------------
    # GET → Seat selection page (prefill from query params)
    # -----------------------------------
    prefill = {
        "from": request.GET.get("from", ""),
        "to": request.GET.get("to", ""),
        "fare": request.GET.get("fare", ""),
        "route": request.GET.get("route", ""),
        "departure_time": request.GET.get("departure_time", ""),
        "arrival_time": request.GET.get("arrival_time", ""),
        "return_date": request.GET.get("date", ""),        # FIXED
        "outbound_id": request.GET.get("outbound_id", ""),
    }

    # Fetch already booked seats for this return route/time
    booked = []
    if prefill["route"]:
        try:
            seat_resp = lambda_client.invoke(
                FunctionName="TicketBuddy_GetSeatStatus",
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "route_id": prefill["route"],
                    "departure_time": prefill["departure_time"]
                })
            )
            seat_result = json.loads(seat_resp["Payload"].read())
            booked = seat_result.get("booked_seats", [])
        except:
            booked = []

    return render(request, "buddy/return_seat.html", {
        "prefill": prefill,
        "booked": booked
    })