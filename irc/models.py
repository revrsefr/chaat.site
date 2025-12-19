from django.db import models
from django.utils import timezone


class TelemetrySnapshot(models.Model):
	"""Captures a point-in-time summary of the IRC network."""

	recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
	user_count = models.PositiveIntegerField(default=0)
	channel_count = models.PositiveIntegerField(default=0)
	server_count = models.PositiveIntegerField(default=0)
	operator_count = models.PositiveIntegerField(default=0)
	overview_payload = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["-recorded_at"]

	def __str__(self) -> str:
		return f"Snapshot @ {self.recorded_at:%Y-%m-%d %H:%M:%S}"  # pragma: no cover


class ChannelPeak(models.Model):
	"""Stores snapshot-scoped channel population highs."""

	snapshot = models.ForeignKey(
		TelemetrySnapshot,
		on_delete=models.CASCADE,
		related_name="channel_peaks",
	)
	channel_name = models.CharField(max_length=200, db_index=True)
	topic = models.TextField(blank=True)
	user_count = models.PositiveIntegerField(default=0)
	recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

	class Meta:
		ordering = ["-recorded_at", "-user_count"]
		indexes = [
			models.Index(fields=["channel_name", "recorded_at"]),
		]

	def __str__(self) -> str:
		return f"{self.channel_name} ({self.user_count})"  # pragma: no cover
