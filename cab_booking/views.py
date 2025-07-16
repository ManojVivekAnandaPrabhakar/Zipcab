import requests
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from .forms import CustomUserCreationForm  # ✅ import your custom form


from .models import Booking


# ======================== UTILITY FUNCTIONS ========================

def get_coordinates(address):
    api_key = settings.API_KEY
    url = f"https://api.distancematrix.ai/maps/api/geocode/json?address={address}&key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

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
    api_key = settings.API_KEY
    url = f"https://api.distancematrix.ai/maps/api/distancematrix/json?origins={origin_lat},{origin_lng}&destinations={dest_lat},{dest_lng}&key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()

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


# ======================== CORE VIEWS ========================

def home(request):
    return render(request, 'cab_booking/home.html')


def send_verification_email(request, user):
    current_site = get_current_site(request)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    verification_link = request.build_absolute_uri(
        reverse('activate', kwargs={'uidb64': uid, 'token': token})
    )

    subject = 'Activate Your ZipCab Account'
    message = render_to_string('registration/activation_email.html', {
        'user': user,
        'verification_link': verification_link,
        'domain': current_site.domain,
    })

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)  # ✅ use custom form
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # ✅ deactivate until email confirmed
            user.save()
            send_verification_email(request, user)  # ✅ send email
            messages.success(request, f"Account created for {user.username}! Please verify your email before logging in.")
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CustomUserCreationForm()  # ✅ use custom form
    return render(request, 'cab_booking/register.html', {'form': form})



def activate_account(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save()
            messages.success(request, "✅ Your account has been activated! You can now log in.")
        else:
            messages.info(request, "ℹ️ Your account is already activated.")
        return redirect('login')
    else:
        messages.error(request, "❌ Activation link is invalid or has expired.")
        return render(request, 'registration/activation_failed.html')


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


from django.contrib.auth import get_user_model

def resend_verification(request, user_id):
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        if not user.is_active:
            send_verification_email(request, user)
            messages.success(request, "🔁 A new verification email has been sent.")
        else:
            messages.info(request, "✅ Your account is already active.")
    except User.DoesNotExist:
        messages.error(request, "❌ User not found.")

    return redirect('login')
