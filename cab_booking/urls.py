from django.urls import path
from . import views
from .views import activate_account  # ✅ import activation view

urlpatterns = [
    path('', views.home, name='home'), 
    path('register/', views.register, name='register'), 
    path('book/', views.booking_view, name='book_cab'), 
    path('my_bookings/', views.my_bookings, name='my_bookings'), 

    # ✅ NEW — Email activation route
    path('activate/<uidb64>/<token>/', activate_account, name='activate'),
]
