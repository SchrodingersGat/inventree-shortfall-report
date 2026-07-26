"""API serializers for the ComponentShortfall plugin.

In practice, you would define your custom serializers here.

Ref: https://www.django-rest-framework.org/api-guide/serializers/
"""

import common.serializers
import part.models as part_models
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class ShortfallReportSerializer(serializers.Serializer):
    """Serializer for shortfall report request parameters."""

    def __init__(self, *args, **kwargs):
        """Set horizon_months default from the plugin setting."""
        super().__init__(*args, **kwargs)

        from plugin.registry import registry

        plugin = registry.get_plugin("component-shortfall")
        default_horizon = (
            int(plugin.get_setting("SHORTFALL_HORIZON_MONTHS")) if plugin else 12
        )
        self.fields["horizon_months"].default = default_horizon

    category = serializers.PrimaryKeyRelatedField(
        queryset=part_models.PartCategory.objects.all(),
        many=False,
        required=False,
        allow_null=True,
        label=_("Category"),
        help_text=_("The category for which to retrieve shortfall data"),
    )

    output = common.serializers.DataOutputSerializer(
        read_only=True,
        allow_null=True,
    )

    max_bom_depth = serializers.IntegerField(
        required=False,
        default=50,
        min_value=0,
        max_value=50,
        label=_("Maximum BOM Depth"),
        help_text=_("The maximum depth to traverse the BOM when calculating shortfall"),
    )

    horizon_months = serializers.IntegerField(
        required=False,
        min_value=0,
        label=_("Horizon (Months)"),
        help_text=_(
            "Only consider orders due within this many months (0 = no limit); defaults to the plugin setting"
        ),
    )

    include_build_orders = serializers.BooleanField(
        required=False,
        default=True,
        label=_("Include Build Orders"),
        help_text=_("Whether to include build orders in the shortfall calculation"),
    )

    include_sales_orders = serializers.BooleanField(
        required=False,
        default=True,
        label=_("Include Sales Orders"),
        help_text=_("Whether to include sales orders in the shortfall calculation"),
    )

    def validate(self, data):
        """Validate the provided data."""

        # TODO: Any custom data validation goes here

        return data
