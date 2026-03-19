"""Generate component shortfall reports"""

import structlog

from django.contrib.auth.models import Group

from plugin import InvenTreePlugin
from plugin.mixins import ScheduleMixin, SettingsMixin, UrlsMixin, UserInterfaceMixin

from . import PLUGIN_VERSION


logger = structlog.get_logger("inventree.shortfall_report")


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
            "default": True,
            "validator": bool,
        },
        "SHORTFALL_REPORT_DAYS": {
            "name": "Shortfall Report Days",
            "description": "Number of days between automatic shortfall report generation (set to 0 to disable)",
            "default": 7,
            "validator": int,
        },
        "SHORTFALL_REPORT_GROUP": {
            "name": "Shortfall Report Group",
            "description": "User group to send periodic shortfall reports",
            "model": "auth.group",
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

        if not request.user or not request.user.is_authenticated:
            return []

        # Only display for users in the selected group
        if group := self.get_plugin_group():
            if not request.user.groups.filter(pk=group.pk).exists():
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

    def get_plugin_group(self) -> Group | None:
        """Return the user group associated with this plugin, if any."""
        group_id = self.get_setting("SHORTFALL_REPORT_GROUP")

        if not group_id:
            return None

        try:
            group = Group.objects.get(pk=group_id)
            return group
        except (ValueError, Group.DoesNotExist):
            return None

    def periodic_shortfall_report(self):
        """Scheduled task to periodically generate a shortfall report.

        This task is called daily, but uses the SHORTFALL_REPORT_DAYS setting to determine how often to actually generate the report.
        """

        import InvenTree.helpers_email
        import InvenTree.tasks
        from common.models import DataOutput
        from .shortfall import calculate_shortfall, format_shortfall_report_html

        report_period = int(self.get_setting("SHORTFALL_REPORT_DAYS"))

        if report_period <= 0:
            logger.info(
                "Shortfall report generation is disabled (SHORTFALL_REPORT_DAYS <= 0)"
            )
            return

        if not InvenTree.tasks.check_daily_holdoff(
            "component_shortfall_report", report_period
        ):
            logger.info("Shortfall report generation skipped due to holdoff period")
            return

        # Run the report generation task here
        data_output = DataOutput.objects.create(
            user=None,
            total=0,
            progress=0,
            output_type="shortfall_report",
            plugin=self.SLUG,
        )

        hide_no_shortfall = self.get_setting("HIDE_NO_SHORTFALL")

        # Calculate shortfall report with default settings
        requirements = calculate_shortfall(data_output.pk)

        data_output.refresh_from_db()

        users = []

        if group := self.get_plugin_group():
            users = group.user_set.filter(is_active=True)

        recipients = []

        for user in users:
            if email := InvenTree.helpers_email.get_email_for_user(user):
                if email not in recipients:
                    recipients.append(email)

        # Construct the email body
        body = format_shortfall_report_html(
            requirements, data_output, hide_no_shortfall=hide_no_shortfall
        )

        # Send email to users, with the report attached
        if recipients:
            InvenTree.helpers_email.send_email(
                subject="[InvenTree] Component Shortfall Report",
                body="Please find the attached component shortfall report.",
                html_message=body,
                recipients=recipients,
            )

        # Record success for the task
        InvenTree.tasks.record_task_success("component_shortfall_report")
