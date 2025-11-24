from django.shortcuts import render, redirect
from django.contrib import messages
from .cognito_auth import cognito_signup, cognito_confirm, cognito_login
import boto3
from django.contrib import messages
import json



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
        data = {
            "username": request.session.get("username"),
            "from": request.POST.get("from"),
            "to": request.POST.get("to"),
            "ticket_type": request.POST.get("ticket_type"),
            "passengers": request.POST.get("passengers"),
            "departure_date": request.POST.get("departure_date"),
            "return_date": request.POST.get("return_date")
        }

        response = lambda_client.invoke(
            FunctionName="TicketBuddy_BookTicket",
            InvocationType="RequestResponse",
            Payload=json.dumps(data)
        )

        result = json.loads(response['Payload'].read())

        if result.get("status") == "success":
            messages.success(request, "Ticket booked successfully!")
        else:
            messages.error(request, "Failed to book ticket.")

        return redirect("book-ticket")

    return render(request, "buddy/booking.html")

def history_page(request):
    return render(request, "buddy/history.html")

def alerts_page(request):
    return render(request, "buddy/alerts.html")

def profile_view(request):
    return render(request, "buddy/profile.html")