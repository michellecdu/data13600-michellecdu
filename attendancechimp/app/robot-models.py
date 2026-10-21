# LLM Version: ChatGPT, GPT-6
# Prompt:
# Generate code for an attendance taking django app (will be under /apps/models.py) with the following entities: 
# • InstructorProfile / StudentProfile tables
# • Course table with at least name, instructor, meeting schedule
# • Enrollment table: links students to courses (many-to-many)
# • Lecture table: linked to a course, has a date and a QR identifier
# • QRCodeUpload table: linked to a student and (optionally) a lecture
# Prioritize complexity and thoroughness, so we don't have to edit the file afterwards.
"""
Django models for a QR-code-based attendance management system.

Core entities:
    - InstructorProfile
    - StudentProfile
    - Course
    - Enrollment
    - Lecture
    - QRCodeUpload

Designed for Django 4.2+ and 5.x.
Uses Django's built-in authentication User model.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models import Q
from django.utils import timezone


# ---------------------------------------------------------------------
# Abstract base model
# ---------------------------------------------------------------------

class TimestampedModel(models.Model):
    """Reusable creation and modification timestamps."""

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------
# Instructor profile
# ---------------------------------------------------------------------

class InstructorProfile(TimestampedModel):
    """
    Additional information for an instructor.

    Each instructor profile belongs to one Django authentication user.
    An instructor can teach multiple courses.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="instructor_profile",
    )

    employee_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
    )

    department = models.CharField(
        max_length=150,
        blank=True,
    )

    office_location = models.CharField(
        max_length=150,
        blank=True,
    )

    phone_number = models.CharField(
        max_length=30,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]
        verbose_name = "Instructor profile"
        verbose_name_plural = "Instructor profiles"
        indexes = [
            models.Index(
                fields=["is_active"],
                name="instr_active_idx",
            ),
        ]

    def __str__(self):
        full_name = self.user.get_full_name()
        return full_name or self.user.get_username()


# ---------------------------------------------------------------------
# Student profile
# ---------------------------------------------------------------------

class StudentProfile(TimestampedModel):
    """
    Additional information for a student.

    A student can enroll in multiple courses through Enrollment.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )

    student_id = models.CharField(
        max_length=50,
        unique=True,
    )

    major = models.CharField(
        max_length=150,
        blank=True,
    )

    academic_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(10),
        ],
        help_text="Student's current year of study, if applicable.",
    )

    phone_number = models.CharField(
        max_length=30,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]
        verbose_name = "Student profile"
        verbose_name_plural = "Student profiles"
        indexes = [
            models.Index(
                fields=["is_active"],
                name="student_active_idx",
            ),
        ]

    def __str__(self):
        full_name = self.user.get_full_name()
        return f"{full_name or self.user.get_username()} ({self.student_id})"


# ---------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------

class Course(TimestampedModel):
    """
    A course taught by an instructor.

    meeting_schedule is a JSON array of schedule entries, for example:

        [
            {
                "day": "MONDAY",
                "start_time": "09:00",
                "end_time": "10:30",
                "location": "Room 201"
            },
            {
                "day": "WEDNESDAY",
                "start_time": "09:00",
                "end_time": "10:30",
                "location": "Room 201"
            }
        ]

    Schedule validation beyond JSON validity can be implemented in
    a form or serializer, depending on the application's API.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        ARCHIVED = "ARCHIVED", "Archived"

    name = models.CharField(max_length=200)

    code = models.CharField(
        max_length=30,
        unique=True,
        help_text="Unique course code, e.g. CS101 or POLSCI200.",
    )

    description = models.TextField(blank=True)

    instructor = models.ForeignKey(
        InstructorProfile,
        on_delete=models.PROTECT,
        related_name="courses",
    )

    meeting_schedule = models.JSONField(
        default=list,
        blank=True,
        help_text="Recurring meeting days, times, and locations.",
    )

    timezone_name = models.CharField(
        max_length=64,
        default="UTC",
        help_text="IANA timezone, e.g. America/New_York.",
    )

    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="Default classroom or online meeting location.",
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum enrollment; blank means unlimited.",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    class Meta:
        ordering = ["name", "code"]
        indexes = [
            models.Index(
                fields=["instructor", "status"],
                name="course_instr_status_idx",
            ),
            models.Index(
                fields=["start_date", "end_date"],
                name="course_dates_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(start_date__isnull=True)
                    | Q(end_date__isnull=True)
                    | Q(end_date__gte=models.F("start_date"))
                ),
                name="course_end_after_start",
            ),
        ]

    def clean(self):
        super().clean()

        if self.instructor_id and not self.instructor.is_active:
            raise ValidationError({
                "instructor": "The selected instructor is inactive."
            })

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValidationError({
                "end_date": "The end date cannot precede the start date."
            })

        if self.timezone_name:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

            try:
                ZoneInfo(self.timezone_name)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValidationError({
                    "timezone_name": "Enter a valid IANA timezone."
                })

    @property
    def enrolled_student_count(self):
        """Count currently enrolled students."""
        return self.enrollments.filter(
            status=Enrollment.Status.ENROLLED
        ).count()

    def __str__(self):
        return f"{self.code}: {self.name}"


# ---------------------------------------------------------------------
# Enrollment (student <-> course many-to-many relationship)
# ---------------------------------------------------------------------

class Enrollment(TimestampedModel):
    """
    Explicit many-to-many relationship between students and courses.

    A student may have only one enrollment record per course.
    Status changes preserve the enrollment's historical record.
    """

    class Status(models.TextChoices):
        ENROLLED = "ENROLLED", "Enrolled"
        WAITLISTED = "WAITLISTED", "Waitlisted"
        DROPPED = "DROPPED", "Dropped"
        COMPLETED = "COMPLETED", "Completed"

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.PROTECT,
        related_name="enrollments",
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="enrollments",
    )

    enrolled_at = models.DateTimeField(default=timezone.now)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ENROLLED,
        db_index=True,
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_student_course_enrollment",
            ),
        ]
        indexes = [
            models.Index(
                fields=["course", "status"],
                name="enroll_course_status_idx",
            ),
            models.Index(
                fields=["student", "status"],
                name="enroll_student_status_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if self.student_id and not self.student.is_active:
            raise ValidationError({
                "student": "The selected student is inactive."
            })

        if self.course_id and self.course.status in {
            Course.Status.COMPLETED,
            Course.Status.ARCHIVED,
        } and self.status in {
            self.Status.ENROLLED,
            self.Status.WAITLISTED,
        }:
            raise ValidationError({
                "course": "Cannot enroll in a completed or archived course."
            })

    def __str__(self):
        return (
            f"{self.student.student_id} - "
            f"{self.course.code} ({self.status})"
        )


# ---------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------

class Lecture(TimestampedModel):
    """
    One scheduled class meeting for a course.

    qr_identifier is a randomly generated UUID suitable for embedding
    in a QR code. A UUID is an identifier, not by itself a complete
    authorization mechanism.
    """

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        OPEN = "OPEN", "Attendance open"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="lectures",
    )

    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional title, e.g. Week 3: Introduction.",
    )

    date = models.DateField(db_index=True)

    start_time = models.TimeField(
        null=True,
        blank=True,
    )

    end_time = models.TimeField(
        null=True,
        blank=True,
    )

    qr_identifier = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier embedded in the lecture QR code.",
    )

    attendance_opens_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    attendance_closes_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["date", "start_time", "id"]
        indexes = [
            models.Index(
                fields=["course", "date"],
                name="lecture_course_date_idx",
            ),
            models.Index(
                fields=["status", "date"],
                name="lecture_status_date_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(start_time__isnull=True)
                    | Q(end_time__isnull=True)
                    | Q(end_time__gt=models.F("start_time"))
                ),
                name="lecture_end_after_start",
            ),
            models.CheckConstraint(
                condition=(
                    Q(attendance_opens_at__isnull=True)
                    | Q(attendance_closes_at__isnull=True)
                    | Q(
                        attendance_closes_at__gt=models.F(
                            "attendance_opens_at"
                        )
                    )
                ),
                name="lecture_attendance_window_valid",
            ),
        ]

    def clean(self):
        super().clean()

        if self.course_id and self.course.status in {
            Course.Status.COMPLETED,
            Course.Status.ARCHIVED,
        } and self.status not in {
            self.Status.COMPLETED,
            self.Status.CANCELLED,
        }:
            raise ValidationError({
                "course": "Cannot schedule a lecture for a completed "
                          "or archived course."
            })

        if (
            self.attendance_opens_at
            and self.attendance_closes_at
            and self.attendance_closes_at <= self.attendance_opens_at
        ):
            raise ValidationError({
                "attendance_closes_at": (
                    "Attendance must close after it opens."
                )
            })

        if (
            self.start_time
            and self.end_time
            and self.end_time <= self.start_time
        ):
            raise ValidationError({
                "end_time": "The lecture end time must follow its start time."
            })

    @property
    def attendance_is_open(self):
        """
        Check whether attendance can currently be submitted.

        Uses timezone-aware datetimes. The caller must still validate
        enrollment, QR authenticity, and duplicate submissions.
        """
        now = timezone.now()

        if self.status not in {self.Status.SCHEDULED, self.Status.OPEN}:
            return False

        if (
            self.attendance_opens_at
            and now < self.attendance_opens_at
        ):
            return False

        if (
            self.attendance_closes_at
            and now > self.attendance_closes_at
        ):
            return False

        return True

    @property
    def attendance_count(self):
        """Number of accepted attendance records for this lecture."""
        return self.qr_uploads.filter(
            status=QRCodeUpload.Status.ACCEPTED
        ).count()

    def __str__(self):
        return f"{self.course.code} - {self.date} ({self.title or 'Lecture'})"


# ---------------------------------------------------------------------
# QR code upload / attendance submission
# ---------------------------------------------------------------------

class QRCodeUpload(TimestampedModel):
    """
    A student's QR-based attendance submission.

    lecture is optional to support uploads that have not yet been
    associated with a particular lecture.

    uploaded_file is optional because clients may submit the scanned
    QR payload directly instead of uploading an image.

    The server must verify the QR payload before marking a submission
    ACCEPTED. Uploading a file or supplying a UUID alone is not proof
    of attendance.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending verification"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.PROTECT,
        related_name="qr_uploads",
    )

    lecture = models.ForeignKey(
        Lecture,
        on_delete=models.PROTECT,
        related_name="qr_uploads",
        null=True,
        blank=True,
        help_text="Leave empty if the upload is not yet linked to a lecture.",
    )

    uploaded_file = models.FileField(
        upload_to="attendance/qr_uploads/%Y/%m/",
        null=True,
        blank=True,
        help_text="Optional uploaded QR image or supporting file.",
    )

    scanned_identifier = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="UUID decoded from the scanned QR code.",
    )

    submitted_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    rejection_reason = models.CharField(
        max_length=255,
        blank=True,
    )

    # Optional audit metadata. Never trust client-provided values
    # as proof of identity or physical presence.
    submission_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.CharField(
        max_length=512,
        blank=True,
    )

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "lecture"],
                condition=Q(lecture__isnull=False),
                name="unique_student_lecture_submission",
            ),
        ]
        indexes = [
            models.Index(
                fields=["lecture", "status"],
                name="qr_lecture_status_idx",
            ),
            models.Index(
                fields=["student", "submitted_at"],
                name="qr_student_submitted_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if self.lecture_id:
            if self.student_id and not Enrollment.objects.filter(
                student_id=self.student_id,
                course_id=self.lecture.course_id,
                status=Enrollment.Status.ENROLLED,
            ).exists():
                raise ValidationError({
                    "student": (
                        "The student must be actively enrolled in "
                        "the lecture's course."
                    )
                })

            if (
                self.scanned_identifier
                and self.scanned_identifier != self.lecture.qr_identifier
            ):
                raise ValidationError({
                    "scanned_identifier": (
                        "The scanned QR identifier does not match "
                        "the selected lecture."
                    )
                })

        if self.status == self.Status.ACCEPTED and not self.lecture_id:
            raise ValidationError({
                "lecture": "An accepted attendance submission must "
                           "be linked to a lecture."
            })

        if self.status == self.Status.ACCEPTED and not self.verified_at:
            raise ValidationError({
                "verified_at": "Accepted submissions must have a "
                               "verification timestamp."
            })

        if self.status == self.Status.REJECTED and not self.rejection_reason:
            raise ValidationError({
                "rejection_reason": "Provide a reason for rejection."
            })

    def mark_accepted(self):
        """
        Mark a submission accepted after the calling service has
        authenticated the user, validated the QR code and time window,
        and checked enrollment.

        Call within transaction.atomic() and handle IntegrityError
        for concurrent duplicate submissions.
        """
        if not self.lecture_id:
            raise ValidationError(
                "A lecture must be assigned before acceptance."
            )

        if self.status in {self.Status.REJECTED, self.Status.EXPIRED}:
            raise ValidationError(
                "Rejected or expired submissions cannot be accepted."
            )

        if not self.lecture.attendance_is_open:
            raise ValidationError(
                "Attendance is not currently open for this lecture."
            )

        if not self.scanned_identifier:
            raise ValidationError(
                "A scanned QR identifier is required."
            )

        if self.scanned_identifier != self.lecture.qr_identifier:
            raise ValidationError(
                "The scanned QR identifier is invalid for this lecture."
            )

        if not Enrollment.objects.filter(
            student=self.student,
            course=self.lecture.course,
            status=Enrollment.Status.ENROLLED,
        ).exists():
            raise ValidationError(
                "The student is not actively enrolled in this course."
            )

        self.status = self.Status.ACCEPTED
        self.verified_at = timezone.now()
        self.rejection_reason = ""
        self.full_clean()
        self.save(
            update_fields=[
                "status",
                "verified_at",
                "rejection_reason",
                "updated_at",
            ]
        )

    def mark_rejected(self, reason):
        """Reject a submission with an auditable reason."""
        if not reason or not reason.strip():
            raise ValidationError("A rejection reason is required.")

        if self.status == self.Status.ACCEPTED:
            raise ValidationError(
                "Accepted attendance cannot be rejected by this method."
            )

        self.status = self.Status.REJECTED
        self.rejection_reason = reason.strip()[:255]
        self.verified_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                "status",
                "rejection_reason",
                "verified_at",
                "updated_at",
            ]
        )

    def __str__(self):
        lecture_label = (
            str(self.lecture)
            if self.lecture_id
            else "Unassigned lecture"
        )
        return (
            f"{self.student.student_id} - {lecture_label} "
            f"[{self.status}]"
        )
