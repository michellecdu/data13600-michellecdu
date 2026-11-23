"""
models.py — Data model for AttendanceChimp.

AttendanceChimp is an electronic class attendance tool.  Instructors create
courses and lectures; each lecture is assigned a random QR code.  Students
photograph the QR code and upload the image.  The system decodes the QR code,
matches it to a lecture, and records the attendance.

Entities
--------
- CourseProfile   : extends Django User → instructor-specific data
- StudentProfile  : extends Django User → student-specific data
- Course          : a course taught by one instructor
- Enrollment      : junction table linking students to courses
- Lecture         : a single class meeting (has a QR-code identifier)
- QRCodeUpload    : a student's uploaded QR-code photograph
"""

from PIL import Image
import pyzbar.pyzbar

from django.db import models
from django.contrib.auth.models import User

import logging
import string
import random
import zoneinfo

CDT = zoneinfo.ZoneInfo("America/Chicago")

logger = logging.getLogger(__name__) # set up tracking, auditing, and debugging
                                                               # allows using logger.warning(), logger.error(), 
                                                               # logger.info(), etc. Better than print() for debuggin... 


# ---------------------------------------------------------------------------
# User profiles
# ---------------------------------------------------------------------------

class StudentProfile(models.Model):
    """
    Student user, linked to uploads (attendance) and enrollments.
    """
    first_name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

class InstructorProfile(models.Model):
    """
    Instructor user, each instructor can teach multiple courses.
    """
    first_name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------

class Course(models.Model):
    """
    Courses are taught by one instructor with a weekly meeting schedule.
    """
    name = models.CharField(max_length=100)
    instructor = models.ForeignKey(InstructorProfile, on_delete=models.CASCADE)
    meeting_days = models.CharField(max_length=10)  # "MWF" or "TR"
    time_start = models.TimeField()
    time_end = models.TimeField()

# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

class Enrollment(models.Model):
    """
    Links students to courses they are enrolled in (many-to-many).
    """
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    class Meta:  # ensure that each (student, course) pair is unique
        constraints = [
            models.UniqueConstraint(fields=['student', 'course'], name='unique_enrollment')
        ]

# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

class Lecture(models.Model):
    """
    Single class lecture, with qr_code as the identifier for the projected QR image.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    lecture_date = models.DateField()
    qr_code = models.CharField(max_length=32, unique=True)

# ---------------------------------------------------------------------------
# QR Code Upload
# ---------------------------------------------------------------------------

class QRCodeUpload(models.Model):
    """
    Stores QR code uploads by students every lecture.
    """
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    lecture = models.ForeignKey(Lecture, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='uploads/')
    upload_timestamp = models.DateTimeField(auto_now_add=True)

# ---------------------------------------------------------------------------
# Helper / API functions
# ---------------------------------------------------------------------------

def is_instructor(user):
    """Check if the user is an instructor."""
    return user.is_authenticated and InstructorProfile.objects.filter(user=user).exists()

def is_student(user):
    """Check if the user is a student."""
    return user.is_authenticated and StudentProfile.objects.filter(user=user).exists()

DAYS = ["M", "T", "W", "R", "F", "S", "U"]

def getUploadsForCourse(course):
    """Return all QRCodeUpload objects for a given course with validation."""
    
    course_obj = Course.objects.filter(name=course).first()
    if course_obj is None:
        return []
    
    valid_uploads = []
    all_uploads = QRCodeUpload.objects.filter(lecture__course=course_obj)
    for upload in all_uploads:
        local_time = upload.upload_timestamp.astimezone(CDT)
        day = DAYS[local_time.weekday()]
        meets_today = day in course_obj.meeting_days
        in_class = course_obj.time_start <= local_time.time() <= course_obj.time_end
        if meets_today and in_class:
            valid_uploads.append(upload)
    return valid_uploads

def decodeQR(image):
    """Decode a QR code from an image file, if possible."""
    try:
        file = Image.open(image)
        results = pyzbar.pyzbar.decode(file)
    except Exception:
        return None
    try:
        decoded_file = results[0].data.decode("utf-8")
    except IndexError:
        return None
    return decoded_file
