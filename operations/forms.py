from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    Asset,
    Expedition,
    InventoryItem,
    LogisticsPlan,
    MaintenanceTask,
    Shipment,
    TeamMember,
    UserProfile,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css_class}".strip()
            if isinstance(field.widget, forms.DateInput):
                field.widget.attrs["type"] = "date"
            elif isinstance(field.widget, forms.DateTimeInput):
                field.widget.attrs["type"] = "datetime-local"


class ExpeditionForm(StyledModelForm):
    class Meta:
        model = Expedition
        fields = ["name", "destination", "start_date", "expected_completion", "leader", "required_equipment", "status", "notes"]
        widgets = {
            "start_date": forms.DateInput(),
            "expected_completion": forms.DateInput(),
            "required_equipment": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        completion = cleaned_data.get("expected_completion")
        if start and completion and completion < start:
            self.add_error("expected_completion", "Completion date must be on or after the start date.")
        return cleaned_data


class AssetForm(StyledModelForm):
    class Meta:
        model = Asset
        fields = ["name", "category", "serial_number", "purchase_date", "current_location", "expedition", "condition", "availability"]
        widgets = {"purchase_date": forms.DateInput()}


class InventoryItemForm(StyledModelForm):
    class Meta:
        model = InventoryItem
        fields = ["name", "category", "quantity", "reorder_level", "unit", "storage_location", "allocated_quantity", "expedition"]

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        allocated = cleaned_data.get("allocated_quantity")
        if quantity is not None and allocated is not None and allocated > quantity:
            self.add_error("allocated_quantity", "Allocated quantity cannot exceed the total quantity.")
        return cleaned_data


class ShipmentForm(StyledModelForm):
    progress = forms.IntegerField(min_value=0, max_value=100)

    class Meta:
        model = Shipment
        fields = ["name", "origin", "destination", "carrier", "estimated_arrival", "progress", "status", "expedition", "notes"]
        widgets = {"estimated_arrival": forms.DateInput(), "notes": forms.Textarea(attrs={"rows": 3})}


class LogisticsPlanForm(StyledModelForm):
    class Meta:
        model = LogisticsPlan
        fields = ["name", "route", "transport_resource", "departure", "cargo_tonnes", "coordinator", "status", "expedition", "notes"]
        widgets = {
            "departure": forms.DateTimeInput(format="%Y-%m-%dT%H:%M"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class TeamMemberForm(StyledModelForm):
    class Meta:
        model = TeamMember
        fields = ["full_name", "designation", "email", "phone", "expedition", "current_location", "availability"]


class MaintenanceTaskForm(StyledModelForm):
    class Meta:
        model = MaintenanceTask
        fields = ["title", "asset", "maintenance_type", "assigned_to", "due_date", "priority", "status", "notes"]
        widgets = {"due_date": forms.DateInput(), "notes": forms.Textarea(attrs={"rows": 3})}


class RegistrationForm(UserCreationForm):
    email = forms.EmailField()
    role = forms.ChoiceField(choices=UserProfile.Role.choices)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email", "role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = UserProfile.Role.choices[1:]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
