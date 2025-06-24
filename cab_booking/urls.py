from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='home'), 
    path('register/', views.register, name='register'), 
    path('book/', views.booking_view, name='book_cab'), 
    path('my_bookings/', views.my_bookings, name='my_bookings'), 
]