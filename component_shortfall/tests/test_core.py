"""Regression tests for the ComponentShortfall plugin class itself (`core.py`)."""

from django.contrib.auth.models import AnonymousUser, Group

from plugin.registry import registry

from InvenTree.unit_test import InvenTreeTestCase


class FakeRequest:
    """Minimal stand-in for a Django request - only `.user` is used by `get_ui_dashboard_items`."""

    def __init__(self, user):
        self.user = user


class GetPluginGroupTests(InvenTreeTestCase):
    """Tests for `ComponentShortfall.get_plugin_group`."""

    def setUp(self):
        super().setUp()
        self.plugin = registry.get_plugin('component-shortfall')

    def tearDown(self):
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', None)
        super().tearDown()

    def test_no_group_configured_returns_none(self):
        """No SHORTFALL_REPORT_GROUP setting -> None."""
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', None)
        self.assertIsNone(self.plugin.get_plugin_group())

    def test_invalid_group_id_returns_none(self):
        """A SHORTFALL_REPORT_GROUP pointing at a non-existent group -> None (handled gracefully)."""
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', 999999)
        self.assertIsNone(self.plugin.get_plugin_group())

    def test_valid_group_id_returns_group(self):
        """A valid SHORTFALL_REPORT_GROUP setting -> the corresponding Group instance."""
        group = Group.objects.create(name='Shortfall Notify Group')
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', group.pk)
        self.assertEqual(self.plugin.get_plugin_group(), group)


class GetUiDashboardItemsTests(InvenTreeTestCase):
    """Tests for `ComponentShortfall.get_ui_dashboard_items`."""

    def setUp(self):
        super().setUp()
        self.plugin = registry.get_plugin('component-shortfall')

    def tearDown(self):
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', None)
        super().tearDown()

    def test_unauthenticated_user_sees_no_items(self):
        """An unauthenticated (anonymous) user is never shown the dashboard item."""
        request = FakeRequest(AnonymousUser())
        items = self.plugin.get_ui_dashboard_items(request, {})
        self.assertEqual(items, [])

    def test_none_user_sees_no_items(self):
        """A missing/None user is handled gracefully, not shown the dashboard item."""
        request = FakeRequest(None)
        items = self.plugin.get_ui_dashboard_items(request, {})
        self.assertEqual(items, [])

    def test_authenticated_user_sees_item_when_no_group_restriction(self):
        """With no SHORTFALL_REPORT_GROUP configured, any authenticated user sees the item."""
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', None)
        request = FakeRequest(self.user)
        items = self.plugin.get_ui_dashboard_items(request, {})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['key'], 'component-shortfall-dashboard')

    def test_group_member_sees_item(self):
        """A user who is a member of the configured group sees the dashboard item."""
        # self.group is provided by InvenTreeTestCase, with self.user already a member
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', self.group.pk)
        request = FakeRequest(self.user)
        items = self.plugin.get_ui_dashboard_items(request, {})
        self.assertEqual(len(items), 1)

    def test_non_group_member_sees_no_items(self):
        """A user who is not a member of the configured group does not see the dashboard item."""
        other_group = Group.objects.create(name='Some Other Group')
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', other_group.pk)
        request = FakeRequest(self.user)
        items = self.plugin.get_ui_dashboard_items(request, {})
        self.assertEqual(items, [])
