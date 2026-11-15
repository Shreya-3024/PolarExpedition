import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CodedRecord(models.Model):
    code = models.CharField(max_length=24, unique=True, blank=True)

    class Meta:
        abstract = True

    code_prefix = "REC"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"{self.code_prefix}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class Expedition(CodedRecord):
    code_prefix = "EXP"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        DELAYED = "delayed", "Delayed"

    name = models.CharField(max_length=160)
    destination = models.CharField(max_length=160)
    start_date = models.DateField()
    expected_completion = models.DateField()
    leader = models.CharField(max_length=120)
    required_equipment = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date", "name"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class TeamMember(CodedRecord):
    code_prefix = "EMP"

    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        PREPARING = "preparing", "Preparing"
        DEPLOYED = "deployed", "Deployed"
        LEAVE = "leave", "On leave"

    full_name = models.CharField(max_length=120)
    designation = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    expedition = models.ForeignKey(
        Expedition, related_name="team_members", on_delete=models.SET_NULL, null=True, blank=True
    )
    current_location = models.CharField(max_length=120, blank=True)
    availability = models.CharField(
        max_length=16, choices=Availability.choices, default=Availability.AVAILABLE
    )

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Asset(CodedRecord):
    code_prefix = "AST"

    class Condition(models.TextChoices):
        EXCELLENT = "excellent", "Excellent"
        GOOD = "good", "Good"
        SERVICE_DUE = "service_due", "Service due"
        DAMAGED = "damaged", "Damaged"

    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        DEPLOYED = "deployed", "Deployed"
        MAINTENANCE = "maintenance", "Maintenance"

    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    serial_number = models.CharField(max_length=100, unique=True)
    purchase_date = models.DateField(null=True, blank=True)
    current_location = models.CharField(max_length=120)
    expedition = models.ForeignKey(
        Expedition, related_name="assets", on_delete=models.SET_NULL, null=True, blank=True
    )
    condition = models.CharField(max_length=16, choices=Condition.choices, default=Condition.GOOD)
    availability = models.CharField(
        max_length=16, choices=Availability.choices, default=Availability.AVAILABLE
    )

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        previous = None
        if self.pk:
            previous = Asset.objects.filter(pk=self.pk).values(
                "name", "condition", "availability", "current_location", "expedition__name"
            ).first()
        super().save(*args, **kwargs)
        if previous is None:
            summary = "Asset registered."
        else:
            current = {
                "name": self.name,
                "condition": self.get_condition_display(),
                "availability": self.get_availability_display(),
                "current_location": self.current_location,
                "expedition__name": self.expedition.name if self.expedition_id else "Unassigned",
            }
            labels = {"name": "Name", "condition": "Condition", "availability": "Availability", "current_location": "Location", "expedition__name": "Expedition"}
            choice_labels = {
                "condition": dict(self.Condition.choices),
                "availability": dict(self.Availability.choices),
            }
            changes = [
                f"{labels[key]} changed from {choice_labels.get(key, {}).get(previous[key], previous[key]) or 'Unassigned'} to {current[key]}"
                for key in labels
                if previous[key] != (
                    current[key]
                    if key == "expedition__name"
                    else getattr(self, key)
                )
            ]
            if not changes:
                return
            summary = "; ".join(changes)
        AssetHistory.objects.create(asset=self, summary=summary)

    def __str__(self):
        return f"{self.code} — {self.name}"


class AssetHistory(models.Model):
    asset = models.ForeignKey(Asset, related_name="history", on_delete=models.CASCADE)
    summary = models.CharField(max_length=400)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurred_at", "-pk"]

    def __str__(self):
        return f"{self.asset.code}: {self.summary}"


class InventoryItem(CodedRecord):
    code_prefix = "INV"

    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)
    unit = models.CharField(max_length=32, default="units")
    storage_location = models.CharField(max_length=120)
    allocated_quantity = models.PositiveIntegerField(default=0)
    expedition = models.ForeignKey(
        Expedition, related_name="inventory_items", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        alert_title = f"Low stock: {self.code}"
        alert = Notification.objects.filter(title=alert_title).first()
        if self.quantity <= self.reorder_level:
            severity = (
                Notification.Severity.CRITICAL
                if self.quantity == 0
                else Notification.Severity.WARNING
            )
            Notification.objects.update_or_create(
                title=alert_title,
                defaults={
                    "message": f"{self.name} has {self.quantity} {self.unit} remaining; reorder level is {self.reorder_level}.",
                    "severity": severity,
                    "is_read": False,
                    "related_url": "/inventory/",
                },
            )
        elif alert and not alert.is_read:
            alert.is_read = True
            alert.save(update_fields=["is_read"])

    @property
    def stock_status(self):
        if self.quantity == 0:
            return "Critical"
        if self.quantity <= self.reorder_level:
            return "Low stock"
        return "In stock"

    def __str__(self):
        return f"{self.code} — {self.name}"


class Shipment(CodedRecord):
    code_prefix = "SHP"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPATCHED = "dispatched", "Dispatched"
        IN_TRANSIT = "in_transit", "In Transit"
        DELIVERED = "delivered", "Delivered"
        DELAYED = "delayed", "Delayed"

    name = models.CharField(max_length=160)
    origin = models.CharField(max_length=120)
    destination = models.CharField(max_length=120)
    carrier = models.CharField(max_length=120)
    estimated_arrival = models.DateField()
    progress = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    expedition = models.ForeignKey(
        Expedition, related_name="shipments", on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["estimated_arrival"]

    def save(self, *args, **kwargs):
        previous = None
        if self.pk:
            previous = Shipment.objects.filter(pk=self.pk).values(
                "status", "progress", "origin", "destination"
            ).first()
        super().save(*args, **kwargs)
        if previous is None:
            summary = f"Shipment registered as {self.get_status_display()}."
        else:
            changes = []
            if previous["status"] != self.status:
                changes.append(f"Status changed to {self.get_status_display()}")
            if previous["progress"] != self.progress:
                changes.append(f"Route progress updated to {self.progress}%")
            if previous["origin"] != self.origin or previous["destination"] != self.destination:
                changes.append(f"Route updated to {self.origin} → {self.destination}")
            if not changes:
                return
            summary = "; ".join(changes)
        ShipmentHistory.objects.create(
            shipment=self,
            summary=summary,
            status=self.status,
            progress=self.progress,
        )

    def __str__(self):
        return f"{self.code} — {self.name}"


class ShipmentHistory(models.Model):
    shipment = models.ForeignKey(Shipment, related_name="history", on_delete=models.CASCADE)
    summary = models.CharField(max_length=300)
    status = models.CharField(max_length=16, choices=Shipment.Status.choices)
    progress = models.PositiveSmallIntegerField(default=0)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurred_at", "-pk"]

    def __str__(self):
        return f"{self.shipment.code}: {self.summary}"


class LogisticsPlan(CodedRecord):
    code_prefix = "LOG"

    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        CONFIRMED = "confirmed", "Confirmed"
        AT_RISK = "at_risk", "At risk"
        COMPLETE = "complete", "Complete"

    name = models.CharField(max_length=160)
    route = models.CharField(max_length=180)
    transport_resource = models.CharField(max_length=120)
    departure = models.DateTimeField()
    cargo_tonnes = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    coordinator = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNING)
    expedition = models.ForeignKey(
        Expedition, related_name="logistics_plans", on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["departure"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class MaintenanceTask(CodedRecord):
    code_prefix = "MNT"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        SCHEDULED = "scheduled", "Scheduled"
        OVERDUE = "overdue", "Overdue"
        COMPLETED = "completed", "Completed"

    title = models.CharField(max_length=160)
    asset = models.ForeignKey(Asset, related_name="maintenance_tasks", on_delete=models.CASCADE)
    maintenance_type = models.CharField(max_length=80)
    assigned_to = models.CharField(max_length=120)
    due_date = models.DateField()
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPCOMING)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.code} — {self.title}"


class Notification(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Information"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    title = models.CharField(max_length=160)
    message = models.TextField()
    severity = models.CharField(max_length=12, choices=Severity.choices, default=Severity.INFO)
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    related_url = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMINISTRATOR = "administrator", "Administrator"
        EXPEDITION_MANAGER = "expedition_manager", "Expedition Manager"
        LOGISTICS_OFFICER = "logistics_officer", "Logistics Officer"
        INVENTORY_MANAGER = "inventory_manager", "Inventory Manager"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.LOGISTICS_OFFICER)

    def __str__(self):
        return f"{self.user} — {self.get_role_display()}"
