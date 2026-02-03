from django.conf import settings
from django.db import models
from django.utils import timezone


class UserReport(models.Model):
    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_made",
        verbose_name="User reporting",
    )
    reported = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_received",
        verbose_name="User reported",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    motive = models.TextField(verbose_name="Motif")
    actions_web = models.TextField(blank=True, verbose_name="Actions web")
    actions_irc = models.TextField(blank=True, verbose_name="Actions on IRC services")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_resolved",
        verbose_name="Administrator that resolved this report",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_RESOLVED and self.resolved_at is None:
            self.resolved_at = timezone.now()
        if self.status == self.STATUS_OPEN and self.resolved_at is not None:
            self.resolved_at = None
        if self.resolved_by and self.status != self.STATUS_RESOLVED:
            self.status = self.STATUS_RESOLVED
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Report #{self.pk} - {self.reporter_id} -> {self.reported_id}"
