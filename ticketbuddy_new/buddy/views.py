from django.shortcuts import render, redirect
from django.contrib import messages
from .cognito_auth import cognito_signup, cognito_confirm, cognito_login
import boto3
from django.contrib import messages
import json
from .fares import FARES
from .schedules import SCHEDULES


lambda_client = boto3.client("lambda", region_name="us-east-1")


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
        # seats from hidden input (comma-separated)
        seats_str = request.POST.get("selected_seats","")
        selected_seats = [s for s in seats_str.split(",") if s]
        route = request.POST.get("route") or request.POST.get("route_id")

        # 1) If seats chosen, call UpdateSeat lambda
        if selected_seats and route:
            seat_payload = {"route_id": route, "seats": selected_seats}
            seat_resp = lambda_client.invoke(
                FunctionName="TicketBuddy_UpdateSeat",
                InvocationType="RequestResponse",
                Payload=json.dumps(seat_payload)
            )
            seat_result = json.loads(seat_resp["Payload"].read())
            if seat_result.get("status") != "success":
                messages.error(request, f"Selected seats conflict: {seat_result.get('message')}")
                return redirect(f"/book-ticket?route={route}&from={request.POST.get('from')}&to={request.POST.get('to')}")

            # get booking_id from seat booking (we pass to book_ticket)
            booking_id = seat_result.get("booking_id")

        else:
            booking_id = None

        # 2) Create ticket
        data = {
            "username": request.session.get("username"),
            "from": request.POST.get("from"),
            "to": request.POST.get("to"),
            "passengers": request.POST.get("passengers"),
            "departure_date": request.POST.get("departure_date"),
            "seats": selected_seats,
            "fare": request.POST.get("fare"),
            "route": route,
            "departure_time": request.POST.get("departure_time"),
            "arrival_time": request.POST.get("arrival_time"),
            "booking_id": booking_id
        }

        resp = lambda_client.invoke(
            FunctionName="TicketBuddy_BookTicket",
            InvocationType="RequestResponse",
            Payload=json.dumps(data)
        )
        result = json.loads(resp['Payload'].read())

        if result.get("status") == "success":
            messages.success(request, f"Ticket booked successfully! Booking ID: {result.get('booking_id')}")
            return redirect("history")
        else:
            messages.error(request, "Failed to book ticket.")
            return redirect("book-ticket")

    # GET → render booking page
    prefill = {
        "from": request.GET.get("from",""),
        "to": request.GET.get("to",""),
        "route": request.GET.get("route",""),
        "fare": request.GET.get("fare",""),
        "departure_time": request.GET.get("time",""),
        "arrival_time": request.GET.get("arrival","")
    }

    # get booked seats for route (call lambda), swallow errors
    booked = []
    route_key = prefill.get("route")
    if route_key:
        try:
            seat_resp = lambda_client.invoke(FunctionName="TicketBuddy_GetSeatStatus", InvocationType="RequestResponse", Payload=json.dumps({"route_id": route_key}))
            seat_result = json.loads(seat_resp["Payload"].read())
            if seat_result.get("status") == "success":
                booked = seat_result.get("booked_seats", [])
        except Exception:
            booked = []

    return render(request, "buddy/booking.html", {"prefill": prefill, "booked": booked})



def history_page(request):
    username = request.session.get("username")
    response = lambda_client.invoke(FunctionName="TicketBuddy_GetHistory", InvocationType="RequestResponse", Payload=json.dumps({"username": username}))
    result = json.loads(response['Payload'].read())
    bookings = result.get("bookings", []) if result.get("status") == "success" else []
    return render(request, "buddy/history.html", {"bookings": bookings})




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

    if request.method == "POST":
        source = request.POST.get("from")
        destination = request.POST.get("to")

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

    return render(request, "buddy/schedules.html", {"schedules": schedules})



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