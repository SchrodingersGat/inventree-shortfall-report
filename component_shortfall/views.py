"""API views for the ComponentShortfall plugin.

In practice, you would define your custom views here.

Ref: https://www.django-rest-framework.org/api-guide/views/
"""

from rest_framework import permissions
from rest_framework.response import Response
from InvenTree.mixins import CreateAPI

from .serializers import ShortfallReportSerializer


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

        # TODO: Fill out response
        data = {
            'part': part,
            'category': category,
            'include_variants': include_variants,
            'output': None
        }

        return Response(ShortfallReportSerializer(data).data)

