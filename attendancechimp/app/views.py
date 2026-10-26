"""
views.py — HTTP request handlers for AttendanceChimp.

Each view corresponds to one URL endpoint.  Views receive an HTTP request,
interact with the database via models.py, and return an HTTP response.
"""

from django.shortcuts import render, redirect
from django.http import (HttpResponse, HttpResponseForbidden,
                         HttpResponseBadRequest, JsonResponse)
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from datetime import datetime
from django.views.decorators.http import require_GET, require_POST
import zoneinfo
import json
import io

from app.models import InstructorProfile, StudentProfile

# from .models import (InstructorProfile, StudentProfile, Course, Enrollment,
#                      Lecture, QRCodeUpload, is_instructor, is_student,
#                      getUploadsForCourse)

CDT = zoneinfo.ZoneInfo("America/Chicago")

# ---------------------------------------------------------------------------
# HW2  — index, time, sum
# ---------------------------------------------------------------------------

def index(request):
    """Render the home page (index.html) with current Chicago time and logged-in user."""
    current_time = datetime.now(CDT).strftime("%H:%M")
    context = {"time": current_time, "user": request.user}
    return render(request, 'app/index.html', context)


def time_view(request):
    """Return the current Chicago time as HH:MM."""
    time = datetime.now(zoneinfo.ZoneInfo("America/Chicago"))
    return HttpResponse(time.strftime("%H:%M"))

def sum_view(request):
    """Receives two numbers and returns sum."""
    a = float(request.GET.get('n1', 0))
    b = float(request.GET.get('n2', 0))
    total = a + b
    if total.is_integer():
        total = int(total)
    return HttpResponse(f"<p>{total}</p>")

# ---------------------------------------------------------------------------
# HW4  — user creation
# ---------------------------------------------------------------------------

# Display the form first 
@require_GET
def new(request):
    """Display the sign-up form, GET only."""
    return render(request, 'app/new.html')

@csrf_exempt
@require_POST
def createUser(request):
    """Create a new user."""
    user_name = request.POST.get('user_name', '')
    password = request.POST.get('password', '')
    email = request.POST.get('email', '')
    is_student = request.POST.get('is_student') == '1'
    if User.objects.filter(email=email).exists():
        return HttpResponseBadRequest("Email already exists.")
    if User.objects.filter(username=user_name).exists():
        return HttpResponseBadRequest("Username already exists.")
    user = User.objects.create_user(username=user_name, password=password, email=email)
    if is_student:
        StudentProfile.objects.create(user=user)
    else:
        InstructorProfile.objects.create(user=user)
    login(request, user)
    return HttpResponse("User successfully created", status=200)

# ---------------------------------------------------------------------------
# HW5  — courses, lectures, QR uploads, dump
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# HW6  — getUploads
# ---------------------------------------------------------------------------



