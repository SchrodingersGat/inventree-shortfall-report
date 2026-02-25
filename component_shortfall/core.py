"""Generate component shortfall reports"""

from plugin import InvenTreePlugin

from plugin.mixins import SettingsMixin, UrlsMixin, UserInterfaceMixin

from . import PLUGIN_VERSION


class ComponentShortfall(SettingsMixin, UrlsMixin, UserInterfaceMixin, InvenTreePlugin):
    """ComponentShortfall - custom InvenTree plugin."""

    # Plugin metadata
    TITLE = "Component Shortfall"
    NAME = "ComponentShortfall"
    SLUG = "component-shortfall"
    DESCRIPTION = "Generate component shortfall reports"
    VERSION = PLUGIN_VERSION

    # Additional project information
    AUTHOR = "Oliver Walters"
    WEBSITE = "https://github.com/SchrodingersGat/inventree-shortfall-report"
    LICENSE = "MIT"

    # Optionally specify supported InvenTree versions
    # MIN_VERSION = '0.18.0'
    # MAX_VERSION = '2.0.0'

    # Plugin settings (from SettingsMixin)
    # Ref: https://docs.inventree.org/en/latest/plugins/mixins/settings/
    SETTINGS = {
        "HIDE_NO_SHORTFALL": {
            "name": "Hide No Shortfall",
            "description": "Hide results for parts which have no shortfall",
            "default": False,
            "validator": bool,
        }
    }

    # Custom URL endpoints (from UrlsMixin)
    # Ref: https://docs.inventree.org/en/latest/plugins/mixins/urls/
    def setup_urls(self):
        """Configure custom URL endpoints for this plugin."""
        from django.urls import path
        from .views import ShortfallReportView

        return [
            # Provide path to a simple custom view - replace this with your own views
            path(
                "shortfall/",
                ShortfallReportView.as_view(),
                name="shortfall-report-view",
            ),
        ]

    # User interface elements (from UserInterfaceMixin)
    # Ref: https://docs.inventree.org/en/latest/plugins/mixins/ui/

    # Custom dashboard items
    def get_ui_dashboard_items(self, request, context: dict, **kwargs):
        """Return a list of custom dashboard items to be rendered in the InvenTree user interface."""

        # Example: only display for 'staff' users
        if not request.user or not request.user.is_staff:
            return []

        items = []

        items.append({
            "key": "component-shortfall-dashboard",
            "title": "Shortfall Report",
            "description": "Generate a component shortfall report",
            "icon": "ti:clipboard-check:outline",
            "source": self.plugin_static_file(
                "Dashboard.js:renderComponentShortfallDashboardItem"
            ),
        })

        return items

    def get_ui_spotlight_actions(self, request, context, **kwargs):
        """Return a list of custom spotlight actions to be made available."""
        return [
            {
                "key": "shortfall-action",
                "title": "Shortfall Report",
                "description": "Generate a component shortfall report",
                "icon": "ti:clipboard-check:outline",
                "source": self.plugin_static_file(
                    "Spotlight.js:ComponentShortfallSpotlightAction"
                ),
            }
        ]
