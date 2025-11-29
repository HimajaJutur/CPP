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

        # -----------------------------
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
    
def return_seat_page(request):

    # -----------------------------------
    # POST → book the return ticket
    # -----------------------------------
    if request.method == "POST":

        seats_str = request.POST.get("selected_seats", "")
        seats = [s for s in seats_str.split(",") if s]

        route = request.POST.get("route")
        fare = request.POST.get("fare")
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
