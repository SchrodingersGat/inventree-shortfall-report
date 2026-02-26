"""API views for the ComponentShortfall plugin.

In practice, you would define your custom views here.

Ref: https://www.django-rest-framework.org/api-guide/views/
"""

from rest_framework import permissions
from rest_framework.response import Response
from InvenTree.mixins import CreateAPI
from InvenTree.tasks import offload_task

from common.models import DataOutput
import part.models as part_models
from .serializers import ShortfallReportSerializer
from .shortfall import calculate_shortfall


class ShortfallReportView(CreateAPI):
    """API view to generate a component shortfall report."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ShortfallReportSerializer

    def post(self, request, *args, **kwargs):
        """Handle POST requests to generate a shortfall report."""

        # Validate the incoming request data using the serializer
        serializer = ShortfallReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        part = serializer.validated_data.get("part", None)
        category = serializer.validated_data.get("category", None)

        include_variants = serializer.validated_data["include_variants"]

        part_id_list = []

        # Extract the top-level parts that we are interested in

        if part:
            if include_variants:
                # Find all active assembly variants of the specified part
                part_id_list = [
                    p.pk for p in part.get_descendants(include_self=True)
                    if p.active
                ]
            else:
                part_id_list = [part.pk]
        elif category:
            # Find all child categories
            categories = category.get_descendants(include_self=True)
            
            # Find all active parts within the provided category
            part_id_list = [
                p.pk for p in part_models.Part.objects.filter(
                category__in=categories, active=True
                )
            ]

        data_output = DataOutput.objects.create(
            user=request.user,
            total=len(part_id_list),
            progress=0,
            output_type='shortfall_report',
            plugin='component-shortfall'
        )

        # This report may be expensive to calculate
        # Offload to the background worker process
        offload_task(
            calculate_shortfall,
            component_id_list=part_id_list,
            output_id=data_output.pk,
            group='shortfall_report',
        )

        data = {
            'part': part,
            'category': category,
            'include_variants': include_variants,
            'output': data_output
        }

        return Response(ShortfallReportSerializer(data).data)

