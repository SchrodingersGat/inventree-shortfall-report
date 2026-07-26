"""Regression tests for the scheduled periodic shortfall report (`core.py::periodic_shortfall_report`).

This was previously entirely untested - including across the Phase 2 session
that fixed a real bug in exactly this function (HIDE_NO_SHORTFALL not being
threaded into `calculate_shortfall()`), which nothing would have caught.
"""

from django.core import mail

from common.models import DataOutput
from company.models import Company
from django.contrib.auth import get_user_model
from order.models import SalesOrder, SalesOrderLineItem
from part.models import Part
from plugin.registry import registry
from stock.models import StockItem, StockLocation

from InvenTree.unit_test import InvenTreeTestCase


class PeriodicShortfallReportTestCase(InvenTreeTestCase):
    """Base fixture for scheduled-report tests."""

    def setUp(self):
        super().setUp()

        self.plugin = registry.get_plugin('component-shortfall')

        self.part = Part.objects.create(
            name='SchedPart', purchaseable=True, salable=True
        )
        self.customer = Company.objects.create(name='Customer', is_customer=True)

        # self.user / self.group are provided by InvenTreeTestCase, with the
        # user already a member of the group
        self.plugin.set_setting('SHORTFALL_REPORT_DAYS', 7)
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', self.group.pk)
        self.plugin.set_setting('HIDE_NO_SHORTFALL', True)

    def create_sales_order(self, quantity=10):
        so = SalesOrder.objects.create(
            customer=self.customer,
            reference=f'SO-{SalesOrder.objects.count() + 1:04d}',
        )
        SalesOrderLineItem.objects.create(order=so, part=self.part, quantity=quantity)
        return so


class ScheduleGatingTests(PeriodicShortfallReportTestCase):
    """Tests for whether the scheduled task runs at all."""

    def test_disabled_when_report_days_is_zero(self):
        """SHORTFALL_REPORT_DAYS=0 disables the scheduled report entirely - no output, no email."""
        self.plugin.set_setting('SHORTFALL_REPORT_DAYS', 0)
        self.create_sales_order()

        count_before = DataOutput.objects.count()
        self.plugin.periodic_shortfall_report()

        self.assertEqual(DataOutput.objects.count(), count_before)
        self.assertEqual(len(mail.outbox), 0)

    def test_holdoff_prevents_immediate_repeat_run(self):
        """A second call within the holdoff period does not generate another report."""
        self.create_sales_order()

        self.plugin.periodic_shortfall_report()
        count_after_first = DataOutput.objects.count()
        self.assertEqual(len(mail.outbox), 1)

        self.plugin.periodic_shortfall_report()

        self.assertEqual(DataOutput.objects.count(), count_after_first)
        self.assertEqual(len(mail.outbox), 1)


class EmailRecipientTests(PeriodicShortfallReportTestCase):
    """Tests for recipient gathering - the report should always generate, but only email when there's someone to send to."""

    def test_generates_report_and_emails_group_members(self):
        """A configured group with an active member both generates a report and emails them."""
        self.create_sales_order()

        self.plugin.periodic_shortfall_report()

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(self.user.email, email.to)
        self.assertEqual(email.subject, '[InvenTree] Component Shortfall Report')

        output = DataOutput.objects.latest('pk')
        self.assertTrue(output.complete)

    def test_no_email_when_group_not_configured(self):
        """The report still generates even when no group is configured, but no email is sent."""
        self.plugin.set_setting('SHORTFALL_REPORT_GROUP', None)
        self.create_sales_order()

        self.plugin.periodic_shortfall_report()

        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(DataOutput.objects.exists())

    def test_no_email_when_group_has_no_active_users(self):
        """An inactive group member is excluded from the recipient list, and no email is sent if none remain."""
        self.user.is_active = False
        self.user.save()
        self.create_sales_order()

        self.plugin.periodic_shortfall_report()

        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_recipient_emails_are_deduplicated(self):
        """Two group members sharing the same email address only receive one copy."""
        other_user = get_user_model().objects.create_user(
            username='otheruser', password='password', email=self.user.email
        )
        other_user.groups.add(self.group)

        self.create_sales_order()
        self.plugin.periodic_shortfall_report()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])


class ScheduledReportSettingsTests(PeriodicShortfallReportTestCase):
    """Tests that plugin settings are correctly threaded through the scheduled report."""

    def test_hide_no_shortfall_setting_reaches_scheduled_email(self):
        """Regression test for the Phase 2 bug fix: HIDE_NO_SHORTFALL must reach the scheduled report too."""
        location = StockLocation.objects.create(name='Location')
        StockItem.objects.create(part=self.part, quantity=1000, location=location)
        self.create_sales_order()  # fully covered by stock -> zero shortfall

        self.plugin.set_setting('HIDE_NO_SHORTFALL', False)
        self.plugin.periodic_shortfall_report()

        self.assertEqual(len(mail.outbox), 1)
        html_body = mail.outbox[0].alternatives[0][0]
        self.assertIn('SchedPart', html_body)

    def test_hide_no_shortfall_true_omits_zero_shortfall_part(self):
        """With HIDE_NO_SHORTFALL=True (the default), a zero-shortfall part is omitted from the email."""
        location = StockLocation.objects.create(name='Location')
        StockItem.objects.create(part=self.part, quantity=1000, location=location)
        self.create_sales_order()

        self.plugin.periodic_shortfall_report()

        self.assertEqual(len(mail.outbox), 1)
        html_body = mail.outbox[0].alternatives[0][0]
        self.assertNotIn('SchedPart', html_body)

    def test_parameter_template_setting_applied_by_scheduled_report(self):
        """SHORTFALL_PARAMETER_TEMPLATE is applied by the scheduled report (was always the case, unlike the API path before Phase 2)."""
        from common.models import Parameter, ParameterTemplate
        from django.contrib.contenttypes.models import ContentType

        template = ParameterTemplate.objects.create(
            name='Shortfall', model_type=ContentType.objects.get_for_model(Part)
        )
        self.plugin.set_setting('SHORTFALL_PARAMETER_TEMPLATE', template.pk)

        self.create_sales_order(quantity=7)
        self.plugin.periodic_shortfall_report()

        param = Parameter.objects.get(
            model_type=ContentType.objects.get_for_model(Part),
            model_id=self.part.pk,
            template=template,
        )
        self.assertEqual(param.data, '7')
