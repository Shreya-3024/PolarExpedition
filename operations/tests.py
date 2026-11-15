from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import ExpeditionForm, InventoryItemForm, RegistrationForm
from .models import Asset, Expedition, InventoryItem, Notification, Shipment


class OperationsViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ops-user", password="PolarSafePass!2026")
        self.client.force_login(self.user)
        self.expedition = Expedition.objects.create(
            name="Aurora Survey",
            destination="Dome C",
            start_date=date.today(),
            expected_completion=date.today() + timedelta(days=30),
            leader="Dr. Test",
            status=Expedition.Status.ACTIVE,
        )

    def test_dashboard_requires_login_and_renders_for_authenticated_users(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next=/")

        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aurora Survey")

    def test_expedition_create_update_and_delete(self):
        list_url = reverse("module_list", kwargs={"module": "expeditions"})
        response = self.client.post(
            reverse("module_create", kwargs={"module": "expeditions"}),
            {
                "name": "Svalbard Watch",
                "destination": "Ny-Ålesund",
                "start_date": "2026-12-01",
                "expected_completion": "2027-01-15",
                "leader": "Dr. Polar",
                "required_equipment": "Weather station",
                "status": Expedition.Status.PLANNED,
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Expedition.objects.get(name="Svalbard Watch")
        self.assertTrue(created.code.startswith("EXP-"))

        response = self.client.post(
            reverse("module_update", kwargs={"module": "expeditions", "pk": created.pk}),
            {
                "name": "Svalbard Climate Watch",
                "destination": "Ny-Ålesund",
                "start_date": "2026-12-01",
                "expected_completion": "2027-01-15",
                "leader": "Dr. Polar",
                "required_equipment": "Weather station",
                "status": Expedition.Status.ACTIVE,
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.name, "Svalbard Climate Watch")

        response = self.client.post(
            reverse("module_delete", kwargs={"module": "expeditions", "pk": created.pk})
        )
        self.assertRedirects(response, list_url)
        self.assertFalse(Expedition.objects.filter(pk=created.pk).exists())

    def test_search_and_inventory_status_filters(self):
        response = self.client.get(
            reverse("module_list", kwargs={"module": "expeditions"}),
            {"q": "Dome", "sort": "name", "direction": "desc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["rows"][0]["object"], self.expedition)
        InventoryItem.objects.create(
            name="Medical kits",
            category="Medical",
            quantity=0,
            reorder_level=5,
            storage_location="Secure Store",
        )
        InventoryItem.objects.create(
            name="Meal packs",
            category="Food",
            quantity=100,
            reorder_level=20,
            storage_location="Warehouse",
        )
        response = self.client.get(
            reverse("module_list", kwargs={"module": "inventory"}), {"status": "critical"}
        )
        self.assertContains(response, "Medical kits")
        self.assertNotContains(response, "Meal packs")
        self.assertTrue(Notification.objects.filter(title__startswith="Low stock:").exists())

    def test_registration_cannot_assign_administrator_role(self):
        form = RegistrationForm(
            data={
                "username": "new-ops",
                "first_name": "New",
                "last_name": "User",
                "email": "new@example.org",
                "role": "administrator",
                "password1": "PolarSafePass!2026",
                "password2": "PolarSafePass!2026",
            }
        )
        self.assertFalse(form.is_valid())

    def test_forms_reject_invalid_dates_and_allocations(self):
        expedition_form = ExpeditionForm(
            data={
                "name": "Invalid dates",
                "destination": "Dome C",
                "start_date": "2027-02-01",
                "expected_completion": "2027-01-01",
                "leader": "Dr. Test",
                "status": Expedition.Status.PLANNED,
            }
        )
        self.assertFalse(expedition_form.is_valid())
        self.assertIn("expected_completion", expedition_form.errors)

        inventory_form = InventoryItemForm(
            data={
                "name": "Fuel",
                "category": "Fuel",
                "quantity": 10,
                "reorder_level": 2,
                "unit": "litres",
                "storage_location": "Tank Farm",
                "allocated_quantity": 11,
            }
        )
        self.assertFalse(inventory_form.is_valid())
        self.assertIn("allocated_quantity", inventory_form.errors)

    def test_notification_read_state_and_report_export(self):
        notification = Notification.objects.create(
            title="Weather update",
            message="Wind conditions are changing.",
            severity=Notification.Severity.WARNING,
        )
        response = self.client.post(
            reverse("notifications"), {"notification_id": notification.pk}
        )
        self.assertEqual(response.status_code, 302)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

        export = self.client.get(reverse("report_export"))
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export["Content-Type"], "text/csv")

    def test_asset_and_shipment_records_persist(self):
        asset = Asset.objects.create(
            name="Satellite phone",
            category="Communications",
            serial_number="SAT-007",
            current_location="Station A",
            expedition=self.expedition,
        )
        shipment = Shipment.objects.create(
            name="Resupply Alpha",
            origin="Hobart",
            destination="McMurdo",
            carrier="Polar vessel",
            estimated_arrival=date.today() + timedelta(days=10),
            expedition=self.expedition,
        )
        self.assertEqual(asset.expedition, self.expedition)
        self.assertEqual(shipment.expedition, self.expedition)
        self.assertEqual(asset.history.count(), 1)
        self.assertEqual(shipment.history.count(), 1)
        asset.current_location = "Dome C field camp"
        asset.save(update_fields=["current_location"])
        self.assertEqual(asset.history.count(), 2)
        shipment.progress = 55
        shipment.status = Shipment.Status.IN_TRANSIT
        shipment.save()
        self.assertEqual(shipment.history.count(), 2)
        response = self.client.get(
            reverse("module_detail", kwargs={"module": "shipments", "pk": shipment.pk})
        )
        self.assertContains(response, "Route progress updated to 55%")
        shipment_list = self.client.get(
            reverse("module_list", kwargs={"module": "shipments"})
        )
        self.assertContains(shipment_list, "Live shipment tracking")
        self.assertContains(shipment_list, "55%")

    def test_primary_workspace_pages_render(self):
        for module in (
            "expeditions",
            "assets",
            "inventory",
            "shipments",
            "logistics",
            "team",
            "maintenance",
        ):
            with self.subTest(module=module):
                response = self.client.get(reverse("module_list", kwargs={"module": module}))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Add")

        for url_name in ("reports", "notifications", "settings"):
            with self.subTest(page=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_administrator_can_render_role_settings(self):
        admin = User.objects.create_superuser(
            username="workspace-admin",
            email="admin@example.org",
            password="NorthernX!2026",
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator")

    def test_module_form_and_details_render(self):
        self.assertEqual(
            self.client.get(reverse("module_create", kwargs={"module": "assets"})).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "module_detail",
                    kwargs={"module": "expeditions", "pk": self.expedition.pk},
                )
            ).status_code,
            200,
        )
