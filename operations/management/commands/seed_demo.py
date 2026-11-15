from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from operations.models import (
    Asset,
    AssetHistory,
    Expedition,
    InventoryItem,
    LogisticsPlan,
    MaintenanceTask,
    Notification,
    Shipment,
    ShipmentHistory,
    TeamMember,
)


class Command(BaseCommand):
    help = "Create a small, realistic PolarOps sample dataset."

    def handle(self, *args, **options):
        today = date.today()
        expedition, _ = Expedition.objects.get_or_create(
            code="EXP-2401",
            defaults={
                "name": "Aurora Deep Ice Survey",
                "destination": "Dome C, Antarctica",
                "start_date": today,
                "expected_completion": today + timedelta(days=75),
                "leader": "Dr. Lena Hoffmann",
                "required_equipment": "GPS beacon, satellite phone, ice radar",
                "status": Expedition.Status.ACTIVE,
            },
        )
        svalbard, _ = Expedition.objects.get_or_create(
            code="EXP-2402",
            defaults={
                "name": "Svalbard Climate Watch",
                "destination": "Ny-Ålesund, Arctic",
                "start_date": today + timedelta(days=10),
                "expected_completion": today + timedelta(days=90),
                "leader": "Prof. Elias Nordin",
                "required_equipment": "Weather station, satellite communications kit",
                "status": Expedition.Status.PLANNED,
            },
        )

        assets = []
        asset_rows = [
            ("AST-1048", "Tracked Snow Vehicle 04", "Transport", "PBV-88-104", "McMurdo Station", Asset.Condition.EXCELLENT, Asset.Availability.DEPLOYED, expedition),
            ("AST-1081", "Spectral Ice Analyzer", "Scientific", "SIA-4409", "Equipment Hub A", Asset.Condition.GOOD, Asset.Availability.AVAILABLE, None),
            ("AST-1093", "Iridium Satellite Kit", "Communication", "ISK-2911", "Svalbard Base", Asset.Condition.EXCELLENT, Asset.Availability.RESERVED, svalbard),
            ("AST-1117", "Polar Generator 12kW", "Power", "PG-12-778", "Maintenance Bay", Asset.Condition.SERVICE_DUE, Asset.Availability.MAINTENANCE, None),
        ]
        for code, name, category, serial, location, condition, availability, assigned in asset_rows:
            asset, _ = Asset.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "serial_number": serial,
                    "current_location": location,
                    "condition": condition,
                    "availability": availability,
                    "expedition": assigned,
                },
            )
            if not asset.history.exists():
                AssetHistory.objects.create(asset=asset, summary="Demo asset record initialized.")
            assets.append(asset)

        inventory_rows = [
            ("INV-0081", "Freeze-dried meal packs", "Food", 2840, 250, "packs", "Warehouse North", 1200, expedition),
            ("INV-0138", "Arctic diesel fuel", "Fuel", 18400, 3000, "litres", "Tank Farm 2", 8500, expedition),
            ("INV-0214", "Emergency medical kit", "Medical", 18, 24, "kits", "Secure Store", 12, None),
            ("INV-0301", "Generator air filters", "Spare parts", 7, 12, "units", "Parts Bay", 4, None),
        ]
        for code, name, category, quantity, reorder, unit, location, allocated, assigned in inventory_rows:
            InventoryItem.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "quantity": quantity,
                    "reorder_level": reorder,
                    "unit": unit,
                    "storage_location": location,
                    "allocated_quantity": allocated,
                    "expedition": assigned,
                },
            )

        shipment, _ = Shipment.objects.get_or_create(
            code="SHP-8821",
            defaults={
                "name": "Aurora resupply Alpha",
                "origin": "Hobart, Australia",
                "destination": "McMurdo Station",
                "carrier": "RV Polar Sentinel",
                "estimated_arrival": today + timedelta(days=8),
                "progress": 72,
                "status": Shipment.Status.IN_TRANSIT,
                "expedition": expedition,
            },
        )
        if not shipment.history.exists():
            ShipmentHistory.objects.create(
                shipment=shipment,
                summary="Demo shipment tracking initialized.",
                status=shipment.status,
                progress=shipment.progress,
            )
        delayed_shipment, _ = Shipment.objects.get_or_create(
            code="SHP-8845",
            defaults={
                "name": "Scientific instruments",
                "origin": "Tromsø, Norway",
                "destination": "Ny-Ålesund",
                "carrier": "Arctic Air Cargo",
                "estimated_arrival": today + timedelta(days=4),
                "progress": 48,
                "status": Shipment.Status.DELAYED,
                "expedition": svalbard,
            },
        )
        if not delayed_shipment.history.exists():
            ShipmentHistory.objects.create(
                shipment=delayed_shipment,
                summary="Demo shipment tracking initialized.",
                status=delayed_shipment.status,
                progress=delayed_shipment.progress,
            )

        LogisticsPlan.objects.get_or_create(
            code="LOG-320",
            defaults={
                "name": "McMurdo inland convoy",
                "route": "McMurdo → Dome C",
                "transport_resource": "4 tracked snow vehicles",
                "departure": timezone.now() + timedelta(days=2),
                "cargo_tonnes": Decimal("24.80"),
                "coordinator": "A. Brennan",
                "status": LogisticsPlan.Status.CONFIRMED,
                "expedition": expedition,
            },
        )

        member, _ = TeamMember.objects.get_or_create(
            code="EMP-0142",
            defaults={
                "full_name": "Dr. Lena Hoffmann",
                "designation": "Lead Glaciologist",
                "email": "l.hoffmann@example.org",
                "current_location": "Dome C",
                "availability": TeamMember.Availability.DEPLOYED,
                "expedition": expedition,
            },
        )

        MaintenanceTask.objects.get_or_create(
            code="MNT-5038",
            defaults={
                "title": "Generator fuel system service",
                "asset": assets[-1],
                "maintenance_type": "Corrective",
                "assigned_to": "I. Petrov",
                "due_date": today - timedelta(days=1),
                "priority": MaintenanceTask.Priority.CRITICAL,
                "status": MaintenanceTask.Status.OVERDUE,
            },
        )
        Notification.objects.get_or_create(
            title="Generator maintenance overdue",
            defaults={
                "message": f"{assets[-1].code} requires immediate service at the McMurdo maintenance bay.",
                "severity": Notification.Severity.CRITICAL,
                "related_url": f"/maintenance/",
            },
        )
        Notification.objects.get_or_create(
            title="Shipment delayed by weather",
            defaults={
                "message": "SHP-8845 is on a weather hold near Tromsø.",
                "severity": Notification.Severity.WARNING,
                "related_url": "/shipments/",
            },
        )

        self.stdout.write(self.style.SUCCESS("Sample expeditions, assets, stock, shipments, team, and alerts are ready."))
