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

    part = serializers.PrimaryKeyRelatedField(
        queryset=part_models.Part.objects.all(),
        many=False,
        required=False,
        allow_null=True,
        label=_("Part"),
        help_text=_("The part for which to retrieve shortfall data"),
    )

    category = serializers.PrimaryKeyRelatedField(
        queryset=part_models.PartCategory.objects.all(),
        many=False,
        required=False,
        allow_null=True,
        label=_("Category"),
        help_text=_("The category for which to retrieve shortfall data"),
    )

    include_variants = serializers.BooleanField(
        required=False,
        default=True,
        label=_('Include Variants'),
        help_text=_('Whether to include part variants in the shortfall report'),
    )

    output = common.serializers.DataOutputSerializer(
        read_only=True,
        allow_null=True,
    )