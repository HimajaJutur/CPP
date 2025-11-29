from django.urls import path
from . import views
from .views import return_seat_page

urlpatterns = [
    path('', views.index, name="index"),   # home page
    path('register/', views.register_view, name="register"),
    path('confirm/', views.confirm_view, name="confirm"),
    path('login/', views.login_view, name="login"),
    path('logout/', views.logout_view, name="logout"),
    path('forgot-password/', views.forgot_password_view, name="forgot-password"),
    path('reset-password/', views.reset_password_view, name="reset-password"),
    path('profile/', views.profile_view, name="profile"),
    path('book-ticket/', views.book_ticket_page, name="book-ticket"),
    path('history/', views.history_page, name="history"),
    path('alerts/', views.alerts_page, name="alerts"),
    path('cancel/<str:booking_id>/', views.cancel_ticket, name="cancel-ticket"),
    path("schedules/", views.schedules_page, name="schedules"),
    path('select-seat/', views.select_seat_page, name="select-seat"),
    path("destinations/", views.destinations_page, name="destinations"),
    path("contact/", views.contact_page, name="contact"),
    path("return-seat/", return_seat_page, name="return-seat"),
    
]
    
