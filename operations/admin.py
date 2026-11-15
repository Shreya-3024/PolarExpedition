from django.contrib import admin

from .models import (
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
    UserProfile,
)


@admin.register(Expedition)
class ExpeditionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "destination", "leader", "start_date", "status")
    list_filter = ("status", "destination")
    search_fields = ("code", "name", "destination", "leader")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "current_location", "condition", "availability")
    list_filter = ("category", "condition", "availability")
    search_fields = ("code", "name", "serial_number")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "quantity", "reorder_level", "storage_location")
    list_filter = ("category",)
    search_fields = ("code", "name", "storage_location")


admin.site.register([
    AssetHistory,
    Shipment,
    ShipmentHistory,
    LogisticsPlan,
    TeamMember,
    MaintenanceTask,
    Notification,
    UserProfile,
])
