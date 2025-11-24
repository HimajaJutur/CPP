from django.urls import path
from . import views

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
]
