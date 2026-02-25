"""API serializers for the ComponentShortfall plugin.

In practice, you would define your custom serializers here.

Ref: https://www.django-rest-framework.org/api-guide/serializers/
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

import part.models


class ShortfallReportRequestSerializer(serializers.Serializer):
    """Serializer for shortfall report request parameters."""

    part = serializers.PrimaryKeyRelatedField(
        queryset=part.models.Part.objects.all(),
        many=False,
        required=True,
        label=_("Part"),
        help_text=_("The part for which to retrieve forecasting data"),
    )

    include_variants = serializers.BooleanField(
        required=False,
        default=True,
    )
