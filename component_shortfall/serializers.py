"""API serializers for the ComponentShortfall plugin.

In practice, you would define your custom serializers here.

Ref: https://www.django-rest-framework.org/api-guide/serializers/
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

import common.serializers
import part.models as part_models


class ShortfallReportSerializer(serializers.Serializer):
    """Serializer for shortfall report request parameters."""

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

    def validate(self, data):
        """Validate the provided data."""

        # TODO: Any custom data validation goes here

        return data
