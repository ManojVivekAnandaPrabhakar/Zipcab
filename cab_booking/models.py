from django.db import models
from django.contrib.auth.models import User 

class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vehicle_choice = models.CharField(max_length=50)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    pickup_location = models.CharField(max_length=255)
    drop_location = models.CharField(max_length=255)
    distance_km = models.DecimalField(max_digits=10, decimal_places=2)
    mobile_number = models.CharField(max_length=15) 
    booking_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking by {self.user.username} for {self.vehicle_choice} to {self.drop_location}"


    


