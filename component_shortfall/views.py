"""API views for the ComponentShortfall plugin.

In practice, you would define your custom views here.

Ref: https://www.django-rest-framework.org/api-guide/views/
"""

from rest_framework.response import Response

from .serializers import ShortfallReportRequestSerializer

from InvenTree.mixins import CreateAPI


class ShortfallReportView(CreateAPI):
    """API view to generate a component shortfall report."""

    def post(self, request, *args, **kwargs):
        """Handle POST requests to generate a shortfall report."""

        # Validate the incoming request data using the serializer
        serializer = ShortfallReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        part = serializer.validated_data["part"]
        include_variants = serializer.validated_data["include_variants"]

        return Response({
            "message": "oh, ok...",
            "part": part.pk,
            "include_variants": include_variants,
        })
