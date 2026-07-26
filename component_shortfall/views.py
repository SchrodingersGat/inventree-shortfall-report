"""API views for the ComponentShortfall plugin.

In practice, you would define your custom views here.

Ref: https://www.django-rest-framework.org/api-guide/views/
"""

from common.models import DataOutput
from InvenTree.mixins import CreateAPI
from InvenTree.tasks import offload_task
from rest_framework import permissions
from rest_framework.response import Response

from .serializers import ShortfallReportSerializer
from .shortfall import calculate_shortfall, get_plugin


class ShortfallReportView(CreateAPI):
    """API view to generate a component shortfall report."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ShortfallReportSerializer

    def post(self, request, *args, **kwargs):
        """Handle POST requests to generate a shortfall report."""

        plugin = get_plugin()

        if not plugin:
            return Response({"error": "Plugin not found"}, status=404)

        include_supplier_data = bool(plugin.get_setting("INCLUDE_SUPPLIER_DATA"))

        # Validate the incoming request data using the serializer
        serializer = ShortfallReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        category = serializer.validated_data.get("category", None)
        max_bom_depth = serializer.validated_data.get("max_bom_depth", 50)
        horizon_months = serializer.validated_data.get("horizon_months")
        include_build_orders = serializer.validated_data.get(
            "include_build_orders", True
        )
        include_sales_orders = serializer.validated_data.get(
            "include_sales_orders", True
        )

        data_output = DataOutput.objects.create(
            user=request.user,
            total=0,
            progress=0,
            output_type="shortfall_report",
            plugin="component-shortfall",
        )

        # This report may be expensive to calculate
        # Offload to the background worker process
        offload_task(
            calculate_shortfall,
            data_output.pk,
            category_id=category.pk if category else None,
            max_bom_depth=max_bom_depth,
            horizon_months=horizon_months,
            include_build_orders=include_build_orders,
            include_sales_orders=include_sales_orders,
            include_supplier_data=include_supplier_data,
            group="shortfall_report",
        )

        data_output.refresh_from_db()

        data = {"category": category, "output": data_output}

        return Response(ShortfallReportSerializer(data).data)
