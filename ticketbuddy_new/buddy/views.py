from django.http import HttpResponse

def home(request):
    return HttpResponse("TicketBuddy NEW — Buddy app is working!")
