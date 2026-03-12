"""Generate component shortfall reports"""

from plugin import InvenTreePlugin

from plugin.mixins import ScheduleMixin, SettingsMixin, UrlsMixin, UserInterfaceMixin

from . import PLUGIN_VERSION


class ComponentShortfall(
    ScheduleMixin, SettingsMixin, UrlsMixin, UserInterfaceMixin, InvenTreePlugin
):
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

    SCHEDULED_TASKS = {
        "shortfall_report": {"func": "periodic_shortfall_report", "schedule": "D"}
    }

    # Plugin settings (from SettingsMixin)
    # Ref: https://docs.inventree.org/en/latest/plugins/mixins/settings/
    SETTINGS = {
        "HIDE_NO_SHORTFALL": {
            "name": "Hide No Shortfall",
            "description": "Hide results for parts which have no shortfall",
            "default": False,
            "validator": bool,
        },
        "SHORTFALL_REPORT_DAYS": {
            "name": "Shortfall Report Days",
            "description": "Number of days between automatic shortfall report generation (set to 0 to disable)",
            "default": 7,
            "validator": int,
        },
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

    def periodic_shortfall_report(self):
        """Scheduled task to periodically generate a shortfall report.

        This task is called daily, but uses the SHORTFALL_REPORT_DAYS setting to determine how often to actually generate the report.
        """

        import InvenTree.tasks

        report_period = int(self.get_setting("SHORTFALL_REPORT_DAYS"))

        if report_period <= 0:
            return

        if not InvenTree.tasks.check_daily_holdoff(
            "component_shortfall_report", report_period
        ):
            return

        # TODO: Actually run the report generation task here
        print("OK I AM TOTALLY RUNNING THE SHORTFALL REPORT GENERATION TASK!!!")

        # Record success for the task
        InvenTree.tasks.record_task_success("component_shortfall_report")
