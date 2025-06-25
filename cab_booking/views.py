import requests
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required

from django.contrib import messages 
from .models import Booking
from django.conf import settings




def get_coordinates(address):
    
    api_key = settings.API_KEY
    url = f"https://api.distancematrix.ai/maps/api/geocode/json?address={address}&key={api_key}"
    try:
        response = requests.get(url, timeout=10) 
        response.raise_for_status()
        data = response.json()

        
        # print(f"Geocoding API Response for '{address}': {data}")
        

        if data.get('status') == 'OK' and 'result' in data and data['result']:
            location = data['result'][0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            
            error_message = data.get('error_message', 'Unknown geocoding error.')
            if data.get('status') == 'ZERO_RESULTS':
                error_message = "No results found for the given address."
            raise Exception(f"Geocoding failed: {error_message}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error during geocoding: {e}")
    except ValueError:
        raise Exception("Invalid JSON response from geocoding API.")


def get_distance_km(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Calculates the distance in kilometers between two geographical points
    using the Distance Matrix AI API.
    """
    api_key = settings.API_KEY
    url = f"https://api.distancematrix.ai/maps/api/distancematrix/json?origins={origin_lat},{origin_lng}&destinations={dest_lat},{dest_lng}&key={api_key}"
    try:
        response = requests.get(url, timeout=10) 
        data = response.json()

        
        # print(f"Distance API Response for ({origin_lat},{origin_lng}) to ({dest_lat},{dest_lng}): {data}")
        

        if data.get('status') == 'OK' and data['rows'] and data['rows'][0]['elements'] and data['rows'][0]['elements'][0]['status'] == 'OK':
            distance_meters = data['rows'][0]['elements'][0]['distance']['value']
            return distance_meters / 1000
        else:
            error_message = data.get('error_message', 'Unknown distance matrix error.')
            if data.get('rows') and data['rows'][0]['elements'] and data['rows'][0]['elements'][0]['status'] != 'OK':
                error_message = data['rows'][0]['elements'][0]['status']
            raise Exception(f"Distance Matrix failed: {error_message}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error during distance calculation: {e}")
    except ValueError:
        raise Exception("Invalid JSON response from distance matrix API.")


def calculate_price(distance_km, choice):
    
    base_fares = {
        "sedan": 50,
        "suv": 70,
        "coupe": 60,
        "mini van": 65
    }
    per_km_rates = {
        "sedan": 12,
        "suv": 15,
        "coupe": 30,
        "mini van": 13
    }

    
    base_fare = base_fares.get(choice, 50)
    per_km_rate = per_km_rates.get(choice, 12)
    return base_fare + (per_km_rate * distance_km)



def home(request):
    
    return render(request, 'cab_booking/home.html')

def register(request):
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) 
            messages.success(request, f"Account created for {user.username}! You are now logged in.")
            return redirect('home') 
        else:
            
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = UserCreationForm()
    return render(request, 'cab_booking/register.html' , {'form': form})


@login_required 
def booking_view(request):
    
    if request.method == 'POST':
        
        choice = request.POST.get('vehicle_type', '').lower()
        pickup = request.POST.get('pickup_location', '')
        drop = request.POST.get('drop_location', '')
        mobile_number = request.POST.get('mobile_number', '')

        
        if not all([choice, pickup, drop, mobile_number]):
            messages.error(request, "All fields are required.")
            return render(request, 'cab_booking/booking_form.html', {
                'vehicle_type': choice,
                'pickup_location': pickup,
                'drop_location': drop,
                'mobile_number': mobile_number,
            })
        
        if not (mobile_number.isdigit() and len(mobile_number) == 10):
            messages.error(request, "Invalid mobile number. Please enter exactly 10 digits.")
            return render(request, 'cab_booking/booking_form.html', {
                'vehicle_type': choice,
                'pickup_location': pickup,
                'drop_location': drop,
                'mobile_number': mobile_number,
            })

        try:
            
            origin_lat, origin_lng = get_coordinates(pickup)
            dest_lat, dest_lng = get_coordinates(drop)

            
            distance_km = get_distance_km(origin_lat, origin_lng, dest_lat, dest_lng)

            
            total_amt = calculate_price(distance_km, choice)

            
            Booking.objects.create(
                user=request.user, 
                vehicle_choice=choice,
                total_amount=total_amt,
                pickup_location=pickup,
                drop_location=drop,
                distance_km=distance_km,
                mobile_number=mobile_number
            )
            messages.success(request, "Your cab has been booked successfully!")
            return render(request, 'cab_booking/booking_success.html', {
                'distance': f"{distance_km:.2f}",
                'total_amt': f"{total_amt:.2f}",
                'choice': choice,
                'pickup': pickup,
                'drop': drop
            })

        except Exception as e:
            messages.error(request, f"Error processing your request: {e}")
            return render(request, 'cab_booking/booking_form.html', {
                'vehicle_type': choice,
                'pickup_location': pickup,
                'drop_location': drop,
                'mobile_number': mobile_number,
            })

    
    return render(request, 'cab_booking/booking_form.html')


@login_required
def my_bookings(request):


    user_bookings = Booking.objects.filter(user=request.user).order_by('-booking_time')
    return render(request, 'cab_booking/my_bookings.html', {'bookings': user_bookings})
