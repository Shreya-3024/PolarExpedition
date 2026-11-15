from datetime import date, datetime
import csv

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    AssetForm,
    ExpeditionForm,
    InventoryItemForm,
    LogisticsPlanForm,
    MaintenanceTaskForm,
    RegistrationForm,
    ShipmentForm,
    TeamMemberForm,
)
from .models import (
    Asset,
    Expedition,
    InventoryItem,
    LogisticsPlan,
    MaintenanceTask,
    Notification,
    Shipment,
    TeamMember,
    UserProfile,
)


MODULES = {
    "expeditions": {
        "title": "Expedition management",
        "singular": "expedition",
        "model": Expedition,
        "form": ExpeditionForm,
        "search": ["code", "name", "destination", "leader"],
        "status_field": "status",
        "columns": [
            ("code", "Expedition ID"),
            ("name", "Expedition"),
            ("destination", "Destination"),
            ("leader", "Leader"),
            ("start_date", "Start date"),
            ("expected_completion", "Completion"),
            ("status", "Status"),
        ],
    },
    "assets": {
        "title": "Asset management",
        "singular": "asset",
        "model": Asset,
        "form": AssetForm,
        "search": ["code", "name", "category", "serial_number", "current_location"],
        "status_field": "availability",
        "columns": [
            ("code", "Asset ID"),
            ("name", "Asset"),
            ("category", "Category"),
            ("serial_number", "Serial number"),
            ("current_location", "Location"),
            ("condition", "Condition"),
            ("availability", "Availability"),
        ],
    },
    "inventory": {
        "title": "Inventory management",
        "singular": "inventory item",
        "model": InventoryItem,
        "form": InventoryItemForm,
        "search": ["code", "name", "category", "storage_location"],
        "status_field": "stock_status",
        "columns": [
            ("code", "Item ID"),
            ("name", "Item"),
            ("category", "Category"),
            ("quantity", "Available stock"),
            ("unit", "Unit"),
            ("storage_location", "Storage"),
            ("stock_status", "Stock status"),
        ],
    },
    "shipments": {
        "title": "Shipment tracking",
        "singular": "shipment",
        "model": Shipment,
        "form": ShipmentForm,
        "search": ["code", "name", "origin", "destination", "carrier"],
        "status_field": "status",
        "columns": [
            ("code", "Shipment ID"),
            ("name", "Shipment"),
            ("origin", "Origin"),
            ("destination", "Destination"),
            ("carrier", "Carrier"),
            ("estimated_arrival", "ETA"),
            ("status", "Status"),
        ],
    },
    "logistics": {
        "title": "Logistics planning",
        "singular": "logistics plan",
        "model": LogisticsPlan,
        "form": LogisticsPlanForm,
        "search": ["code", "name", "route", "transport_resource", "coordinator"],
        "status_field": "status",
        "columns": [
            ("code", "Plan ID"),
            ("name", "Operation"),
            ("route", "Route"),
            ("transport_resource", "Transport"),
            ("departure", "Departure"),
            ("cargo_tonnes", "Cargo (t)"),
            ("status", "Status"),
        ],
    },
    "team": {
        "title": "Team management",
        "singular": "team member",
        "model": TeamMember,
        "form": TeamMemberForm,
        "search": ["code", "full_name", "designation", "email", "current_location"],
        "status_field": "availability",
        "columns": [
            ("code", "Employee ID"),
            ("full_name", "Team member"),
            ("designation", "Designation"),
            ("email", "Contact"),
            ("expedition", "Expedition"),
            ("current_location", "Location"),
            ("availability", "Availability"),
        ],
    },
    "maintenance": {
        "title": "Maintenance management",
        "singular": "maintenance task",
        "model": MaintenanceTask,
        "form": MaintenanceTaskForm,
        "search": ["code", "title", "asset__name", "assigned_to", "maintenance_type"],
        "status_field": "status",
        "columns": [
            ("code", "Request ID"),
            ("title", "Maintenance task"),
            ("asset", "Asset"),
            ("maintenance_type", "Type"),
            ("assigned_to", "Assigned to"),
            ("due_date", "Due date"),
            ("status", "Status"),
        ],
    },
}


class OperationsLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class OperationsLogoutView(LogoutView):
    pass


login_view = OperationsLoginView.as_view()
logout_view = OperationsLogoutView.as_view()


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.objects.create(user=user, role=form.cleaned_data["role"])
        login(request, user)
        messages.success(request, "Your PolarOps workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


def module_config(module):
    return MODULES.get(module)


def get_display_value(record, field_name):
    if field_name == "stock_status":
        return record.stock_status
    display_method = getattr(record, f"get_{field_name}_display", None)
    value = display_method() if callable(display_method) else getattr(record, field_name)
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return value


def status_filter_options(config):
    model = config["model"]
    field_name = config["status_field"]
    if field_name == "stock_status":
        return [("in_stock", "In stock"), ("low_stock", "Low stock"), ("critical", "Critical")]
    field = model._meta.get_field(field_name)
    return list(field.choices)


def apply_status_filter(queryset, module, status):
    if not status:
        return queryset
    if module == "inventory":
        if status == "critical":
            return queryset.filter(quantity=0)
        if status == "low_stock":
            return queryset.filter(quantity__gt=0, quantity__lte=F("reorder_level"))
        if status == "in_stock":
            return queryset.filter(quantity__gt=F("reorder_level"))
        return queryset.none()
    return queryset.filter(**{MODULES[module]["status_field"]: status})


@login_required
def dashboard(request):
    unread_notifications = Notification.objects.filter(is_read=False).count()
    context = {
        "active_page": "dashboard",
        "active_expeditions": Expedition.objects.filter(status=Expedition.Status.ACTIVE).count(),
        "asset_count": Asset.objects.count(),
        "available_assets": Asset.objects.filter(availability=Asset.Availability.AVAILABLE).count(),
        "deployed_assets": Asset.objects.filter(availability=Asset.Availability.DEPLOYED).count(),
        "assets_in_maintenance": Asset.objects.filter(availability=Asset.Availability.MAINTENANCE).count(),
        "available_inventory": InventoryItem.objects.filter(quantity__gt=F("reorder_level")).count(),
        "shipments_in_transit": Shipment.objects.filter(status=Shipment.Status.IN_TRANSIT).count(),
        "pending_maintenance": MaintenanceTask.objects.exclude(status=MaintenanceTask.Status.COMPLETED).count(),
        "critical_alerts": Notification.objects.filter(
            severity=Notification.Severity.CRITICAL, is_read=False
        ).count(),
        "unread_notifications": unread_notifications,
        "recent_expeditions": Expedition.objects.select_related().all()[:5],
        "recent_shipments": Shipment.objects.all()[:5],
        "tracking_shipments": Shipment.objects.exclude(
            status=Shipment.Status.DELIVERED
        ).order_by("-progress")[:3],
        "upcoming_maintenance": MaintenanceTask.objects.select_related("asset").filter(
            status__in=[MaintenanceTask.Status.UPCOMING, MaintenanceTask.Status.SCHEDULED]
        )[:5],
        "critical_notifications": Notification.objects.filter(
            severity=Notification.Severity.CRITICAL, is_read=False
        ).order_by("-created_at")[:5],
        "expedition_count": Expedition.objects.count(),
        "planned_count": Expedition.objects.filter(status=Expedition.Status.PLANNED).count(),
        "low_stock_count": InventoryItem.objects.filter(quantity__lte=F("reorder_level")).count(),
        "page_title": "Operations overview",
    }
    return render(request, "operations/dashboard.html", context)


@login_required
def module_list(request, module):
    config = module_config(module)
    if config is None:
        return redirect("dashboard")
    queryset = config["model"].objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        search_query = Q()
        for field in config["search"]:
            search_query |= Q(**{f"{field}__icontains": query})
        queryset = queryset.filter(search_query)
    status = request.GET.get("status", "")
    queryset = apply_status_filter(queryset, module, status)
    sort_key = request.GET.get("sort", "")
    sort_direction = request.GET.get("direction", "asc")
    sortable_fields = {
        key for key, _label in config["columns"] if key != "stock_status"
    }
    if sort_key in sortable_fields:
        prefix = "-" if sort_direction == "desc" else ""
        queryset = queryset.order_by(f"{prefix}{sort_key}")
    else:
        sort_key = ""
        sort_direction = "asc"
    page_obj = Paginator(queryset, 10).get_page(request.GET.get("page"))
    rows = [
        {
            "object": record,
            "cells": [
                {"key": key, "value": get_display_value(record, key), "is_code": key == "code"}
                for key, _label in config["columns"]
            ],
        }
        for record in page_obj.object_list
    ]
    return render(
        request,
        "operations/module_list.html",
        {
            "active_page": module,
            "page_title": config["title"],
            "module": module,
            "config": config,
            "headers": [
                {"key": key, "label": label}
                for key, label in config["columns"]
            ],
            "rows": rows,
            "page_obj": page_obj,
            "search_query": query,
            "selected_status": status,
            "status_options": status_filter_options(config),
            "sort_key": sort_key,
            "sort_direction": sort_direction,
            "tracking_shipments": (
                Shipment.objects.exclude(status=Shipment.Status.DELIVERED)
                .order_by("-progress")[:3]
                if module == "shipments"
                else []
            ),
        },
    )


@login_required
def module_form(request, module, instance=None):
    config = module_config(module)
    if config is None:
        return redirect("dashboard")
    editing = instance is not None
    form = config["form"](request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        messages.success(
            request,
            f"{config['singular'].capitalize()} {'updated' if editing else 'created'} successfully.",
        )
        return redirect("module_detail", module=module, pk=record.pk)
    return render(
        request,
        "operations/module_form.html",
        {
            "active_page": module,
            "page_title": f"{'Edit' if editing else 'Add'} {config['singular']}",
            "module": module,
            "config": config,
            "form": form,
            "editing": editing,
        },
    )


@login_required
def module_create(request, module):
    return module_form(request, module)


@login_required
def module_update(request, module, pk):
    config = module_config(module)
    if config is None:
        return redirect("dashboard")
    instance = get_object_or_404(config["model"], pk=pk)
    return module_form(request, module, instance)


@login_required
def module_detail(request, module, pk):
    config = module_config(module)
    if config is None:
        return redirect("dashboard")
    record = get_object_or_404(config["model"], pk=pk)
    details = [
        (label, get_display_value(record, key))
        for key, label in config["columns"]
    ]
    history = None
    if module in {"assets", "shipments"}:
        history = record.history.all()
    return render(
        request,
        "operations/module_detail.html",
        {
            "active_page": module,
            "page_title": f"{config['singular'].capitalize()} details",
            "module": module,
            "config": config,
            "record": record,
            "details": details,
            "history": history,
        },
    )


@login_required
def module_delete(request, module, pk):
    config = module_config(module)
    if config is None:
        return redirect("dashboard")
    record = get_object_or_404(config["model"], pk=pk)
    if request.method == "POST":
        record.delete()
        messages.success(request, f"{config['singular'].capitalize()} deleted.")
        return redirect("module_list", module=module)
    return render(
        request,
        "operations/module_confirm_delete.html",
        {
            "active_page": module,
            "page_title": f"Delete {config['singular']}",
            "module": module,
            "config": config,
            "record": record,
        },
    )


@login_required
def global_search(request):
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        for module, config in MODULES.items():
            search_query = Q()
            for field in config["search"]:
                search_query |= Q(**{f"{field}__icontains": query})
            for record in config["model"].objects.filter(search_query)[:5]:
                results.append(
                    {
                        "module": module,
                        "title": str(record),
                        "subtitle": config["title"],
                        "url": reverse("module_detail", kwargs={"module": module, "pk": record.pk}),
                    }
                )
    return render(
        request,
        "operations/search_results.html",
        {"active_page": "", "page_title": "Search", "query": query, "results": results},
    )


@login_required
def reports(request):
    context = {
        "active_page": "reports",
        "page_title": "Reports & analytics",
        "expedition_total": Expedition.objects.count(),
        "active_expeditions": Expedition.objects.filter(status=Expedition.Status.ACTIVE).count(),
        "asset_total": Asset.objects.count(),
        "deployed_assets": Asset.objects.filter(availability=Asset.Availability.DEPLOYED).count(),
        "inventory_total": InventoryItem.objects.count(),
        "low_stock": InventoryItem.objects.filter(quantity__lte=F("reorder_level")).count(),
        "shipment_total": Shipment.objects.count(),
        "delayed_shipments": Shipment.objects.filter(status=Shipment.Status.DELAYED).count(),
        "maintenance_total": MaintenanceTask.objects.count(),
        "overdue_maintenance": MaintenanceTask.objects.filter(status=MaintenanceTask.Status.OVERDUE).count(),
        "expeditions": Expedition.objects.all()[:8],
    }
    return render(request, "operations/reports.html", context)


@login_required
def report_export(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="polarops-report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Report", "Total", "Attention required"])
    writer.writerow(["Expeditions", Expedition.objects.count(), Expedition.objects.filter(status=Expedition.Status.DELAYED).count()])
    writer.writerow(["Assets", Asset.objects.count(), Asset.objects.filter(availability=Asset.Availability.MAINTENANCE).count()])
    writer.writerow(["Inventory items", InventoryItem.objects.count(), InventoryItem.objects.filter(quantity__lte=F("reorder_level")).count()])
    writer.writerow(["Shipments", Shipment.objects.count(), Shipment.objects.filter(status=Shipment.Status.DELAYED).count()])
    writer.writerow(["Maintenance tasks", MaintenanceTask.objects.count(), MaintenanceTask.objects.filter(status=MaintenanceTask.Status.OVERDUE).count()])
    return response


@login_required
def notifications(request):
    if request.method == "POST":
        notification_id = request.POST.get("notification_id")
        if notification_id:
            Notification.objects.filter(pk=notification_id).update(is_read=True)
        else:
            Notification.objects.filter(is_read=False).update(is_read=True)
        messages.success(request, "Notification status updated.")
        return redirect("notifications")
    return render(
        request,
        "operations/notifications.html",
        {
            "active_page": "notifications",
            "page_title": "Notifications",
            "notifications": Notification.objects.all(),
            "unread_notifications": Notification.objects.filter(is_read=False).count(),
        },
    )


@login_required
def settings_page(request):
    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        request.user.first_name = request.POST.get("first_name", "").strip()
        request.user.last_name = request.POST.get("last_name", "").strip()
        request.user.email = request.POST.get("email", "").strip()
        request.user.save(update_fields=["first_name", "last_name", "email"])
        if request.user.is_staff or request.user.is_superuser:
            role = request.POST.get("role")
            valid_roles = {value for value, _label in UserProfile.Role.choices}
            if role in valid_roles:
                profile.role = role
                profile.save(update_fields=["role"])
        messages.success(request, "Your profile settings were saved.")
        return redirect("settings")
    return render(
        request,
        "operations/settings.html",
        {
            "active_page": "settings",
            "page_title": "Workspace settings",
            "profile": profile,
            "role_options": UserProfile.Role.choices,
        },
    )
