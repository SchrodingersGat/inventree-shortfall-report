"""Regression tests for the core shortfall calculation functions in `shortfall.py`."""

from datetime import date, timedelta
from decimal import Decimal

from build.models import Build
from build.status_codes import BuildStatus
from common.models import DataOutput, Parameter, ParameterTemplate
from django.contrib.contenttypes.models import ContentType
from order.models import SalesOrder, SalesOrderLineItem
from order.status_codes import SalesOrderStatus
from part.models import BomItem, Part
from stock.models import StockItem, StockLocation

from InvenTree.unit_test import InvenTreeTestCase

from .. import shortfall

TOMORROW = date.today() + timedelta(days=1)
NEXT_YEAR = date.today() + timedelta(days=400)


class ShortfallTestCase(InvenTreeTestCase):
    """Base test case which creates a simple assembly for shortfall tests."""

    def setUp(self):
        """Create a simple part hierarchy: assembly -> component."""
        super().setUp()

        self.assembly = Part.objects.create(
            name='Assembly',
            description='Top level assembly',
            assembly=True,
            component=False,
            salable=True,
        )
        self.component = Part.objects.create(
            name='Component',
            description='A component part',
            assembly=False,
            component=True,
            purchaseable=True,
            salable=False,
        )
        # MPTT's tree_id fixup on save is not reflected on the in-memory
        # instance - refresh before using these parts in BomItem creation.
        self.assembly.refresh_from_db()
        self.component.refresh_from_db()

        self.bom_item = BomItem.objects.create(
            part=self.assembly, sub_part=self.component, quantity=2
        )

        self.customer = None

    def get_plugin(self):
        """Return the ComponentShortfall plugin instance."""
        from plugin.registry import registry

        return registry.get_plugin('component-shortfall')


class OutstandingSalesOrderPartsTests(ShortfallTestCase):
    """Tests for `get_outstanding_sales_order_parts`."""

    def setUp(self):
        super().setUp()
        from company.models import Company

        self.customer = Company.objects.create(name='Customer', is_customer=True)

    def create_order(self, part, quantity, shipped=0, target_date=None, status=None):
        """Helper to create a sales order (with the given target date) with a single line item."""
        so = SalesOrder.objects.create(
            customer=self.customer,
            reference=f'SO-{SalesOrder.objects.count() + 1:04d}',
            target_date=target_date,
        )
        if status is not None:
            so.status = status.value
            so.save()

        SalesOrderLineItem.objects.create(
            order=so, part=part, quantity=quantity, shipped=shipped
        )
        return so

    def test_open_order_contributes_required_quantity(self):
        """An open sales order line contributes its outstanding quantity."""
        self.create_order(self.assembly, 10)

        outstanding = shortfall.get_outstanding_sales_order_parts()
        self.assertIn(self.assembly.pk, outstanding)
        self.assertEqual(outstanding[self.assembly.pk]['required'], 10)

    def test_shipped_quantity_is_offset(self):
        """Already-shipped quantity is subtracted from the requirement."""
        self.create_order(self.assembly, 10, shipped=4)

        outstanding = shortfall.get_outstanding_sales_order_parts()
        self.assertEqual(outstanding[self.assembly.pk]['required'], 6)

    def test_fully_shipped_line_excluded(self):
        """A fully-shipped line contributes no requirement."""
        self.create_order(self.assembly, 10, shipped=10)

        outstanding = shortfall.get_outstanding_sales_order_parts()
        self.assertNotIn(self.assembly.pk, outstanding)

    def test_multiple_lines_are_aggregated(self):
        """Multiple order lines for the same part are summed together."""
        self.create_order(self.assembly, 10)
        self.create_order(self.assembly, 5, shipped=1)

        outstanding = shortfall.get_outstanding_sales_order_parts()
        self.assertEqual(outstanding[self.assembly.pk]['required'], 14)

    def test_complete_order_excluded(self):
        """A completed sales order does not contribute to requirements."""
        so = self.create_order(self.assembly, 10)
        so.status = SalesOrderStatus.COMPLETE.value
        so.save()

        outstanding = shortfall.get_outstanding_sales_order_parts()
        self.assertNotIn(self.assembly.pk, outstanding)

    def test_shipped_order_still_included(self):
        """A 'shipped' sales order is still considered open (not yet formally completed)."""
        so = self.create_order(self.assembly, 10)
        so.status = SalesOrderStatus.SHIPPED.value
        so.save()

        outstanding = shortfall.get_outstanding_sales_order_parts()
        self.assertIn(self.assembly.pk, outstanding)

    def test_cancelled_order_excluded(self):
        """A cancelled sales order does not contribute to requirements."""
        so = self.create_order(self.assembly, 10)
        so.status = SalesOrderStatus.CANCELLED.value
        so.save()

        outstanding = shortfall.get_outstanding_sales_order_parts()
        self.assertNotIn(self.assembly.pk, outstanding)

    def test_pending_order_excluded_when_setting_enabled(self):
        """Pending sales orders are excluded when EXCLUDE_PENDING_SALES_ORDERS is set."""
        self.create_order(self.assembly, 10, status=SalesOrderStatus.PENDING)

        plugin = self.get_plugin()
        plugin.set_setting('EXCLUDE_PENDING_SALES_ORDERS', True)
        try:
            outstanding = shortfall.get_outstanding_sales_order_parts()
            self.assertNotIn(self.assembly.pk, outstanding)
        finally:
            plugin.set_setting('EXCLUDE_PENDING_SALES_ORDERS', False)

    def test_horizon_date_excludes_far_future_orders(self):
        """Orders with a target date beyond the horizon are excluded."""
        self.create_order(self.assembly, 10, target_date=NEXT_YEAR)

        outstanding = shortfall.get_outstanding_sales_order_parts(
            horizon_date=TOMORROW
        )
        self.assertNotIn(self.assembly.pk, outstanding)

    def test_horizon_date_includes_undated_orders(self):
        """Orders without a target date are always included, regardless of horizon."""
        self.create_order(self.assembly, 10, target_date=None)

        outstanding = shortfall.get_outstanding_sales_order_parts(
            horizon_date=TOMORROW
        )
        self.assertIn(self.assembly.pk, outstanding)


class OutstandingBuildOrderPartsTests(ShortfallTestCase):
    """Tests for `get_outstanding_build_order_parts`."""

    def create_build(self, quantity=10, completed=0, target_date=None, status=None):
        """Helper to create a build order for the assembly part."""
        build = Build.objects.create(
            part=self.assembly,
            quantity=quantity,
            completed=completed,
            reference=f'BO-{Build.objects.count() + 1:04d}',
            target_date=target_date,
        )
        if status is not None:
            build.status = status.value
            build.save()
        return build

    def get_build_line(self, build):
        """Return the (only) BuildLine for a given build order."""
        return build.build_lines.get(bom_item=self.bom_item)

    def test_active_build_contributes_component_requirement(self):
        """An active build order requires its BOM sub-parts, scaled by quantity."""
        self.create_build(quantity=10)

        outstanding = shortfall.get_outstanding_build_order_parts()
        self.assertIn(self.component.pk, outstanding)
        # 10 assemblies * 2 components each = 20 required
        self.assertEqual(outstanding[self.component.pk]['required'], 20)

    def test_consumed_quantity_is_offset(self):
        """Already-consumed quantity is subtracted from the line requirement."""
        build = self.create_build(quantity=10)
        line = self.get_build_line(build)
        line.consumed = 5
        line.save()

        outstanding = shortfall.get_outstanding_build_order_parts()
        self.assertEqual(outstanding[self.component.pk]['required'], 15)

    def test_fully_consumed_line_excluded(self):
        """A fully-consumed build line contributes no requirement."""
        build = self.create_build(quantity=10)
        line = self.get_build_line(build)
        line.consumed = line.quantity
        line.save()

        outstanding = shortfall.get_outstanding_build_order_parts()
        self.assertNotIn(self.component.pk, outstanding)

    def test_completed_build_excluded(self):
        """A completed build order does not contribute to requirements."""
        build = self.create_build(quantity=10)
        build.status = BuildStatus.COMPLETE.value
        build.save()

        outstanding = shortfall.get_outstanding_build_order_parts()
        self.assertNotIn(self.component.pk, outstanding)

    def test_cancelled_build_excluded(self):
        """A cancelled build order does not contribute to requirements."""
        build = self.create_build(quantity=10)
        build.status = BuildStatus.CANCELLED.value
        build.save()

        outstanding = shortfall.get_outstanding_build_order_parts()
        self.assertNotIn(self.component.pk, outstanding)

    def test_virtual_sub_part_excluded(self):
        """A virtual sub-part referenced by an active build's BuildLine does not contribute a requirement.

        Regression test: virtual sub-parts were already excluded when reached via
        BOM traversal in `calculate_shortfall` (`get_bom_items(include_virtual=False)`),
        but not when directly referenced by a BuildLine here - an inconsistency.
        """
        self.component.virtual = True
        self.component.save()

        self.create_build(quantity=10)

        outstanding = shortfall.get_outstanding_build_order_parts()
        self.assertNotIn(self.component.pk, outstanding)

    def test_pending_build_excluded_when_setting_enabled(self):
        """Pending build orders are excluded when EXCLUDE_PENDING_BUILD_ORDERS is set."""
        self.create_build(quantity=10, status=BuildStatus.PENDING)

        plugin = self.get_plugin()
        plugin.set_setting('EXCLUDE_PENDING_BUILD_ORDERS', True)
        try:
            outstanding = shortfall.get_outstanding_build_order_parts()
            self.assertNotIn(self.component.pk, outstanding)
        finally:
            plugin.set_setting('EXCLUDE_PENDING_BUILD_ORDERS', False)

    def test_horizon_date_excludes_far_future_builds(self):
        """Builds with a target date beyond the horizon are excluded."""
        self.create_build(quantity=10, target_date=NEXT_YEAR)

        outstanding = shortfall.get_outstanding_build_order_parts(
            horizon_date=TOMORROW
        )
        self.assertNotIn(self.component.pk, outstanding)


class OutstandingPartsTests(ShortfallTestCase):
    """Tests for `get_outstanding_parts` (combined sales + build orders)."""

    def setUp(self):
        super().setUp()
        from company.models import Company

        self.customer = Company.objects.create(name='Customer', is_customer=True)

    def test_combines_sales_and_build_requirements(self):
        """Requirements from sales orders and build orders are combined per-part."""
        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.component, quantity=5)

        Build.objects.create(
            part=self.assembly, quantity=3, reference='BO-0001'
        )

        outstanding = shortfall.get_outstanding_parts()

        # Component required: 5 (direct SO) + 6 (3 assemblies * 2 components) = 11
        self.assertEqual(outstanding[self.component.pk]['required'], 11)

    def test_include_sales_orders_false_excludes_sales_requirements(self):
        """Sales order requirements are excluded when include_sales_orders=False."""
        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.component, quantity=5)

        outstanding = shortfall.get_outstanding_parts(include_sales_orders=False)
        self.assertNotIn(self.component.pk, outstanding)

    def test_include_build_orders_false_excludes_build_requirements(self):
        """Build order requirements are excluded when include_build_orders=False."""
        Build.objects.create(part=self.assembly, quantity=3, reference='BO-0001')

        outstanding = shortfall.get_outstanding_parts(include_build_orders=False)
        self.assertNotIn(self.component.pk, outstanding)


class UpdatePartRequirementsTests(ShortfallTestCase):
    """Tests for `update_part_requirements`."""

    def test_first_call_seeds_stock_and_shortfall(self):
        """The first call for a part fetches stock/on_order/in_production and computes shortfall."""
        location = StockLocation.objects.create(name='Location')
        StockItem.objects.create(part=self.component, quantity=5, location=location)

        requirements = {}
        delta = shortfall.update_part_requirements(self.component, 20, requirements)

        data = requirements[self.component.pk]
        self.assertEqual(data['stock'], 5)
        self.assertEqual(data['required'], 20)
        self.assertEqual(data['shortfall'], 15)
        self.assertEqual(delta, 15)

    def test_repeated_calls_accumulate_required_quantity(self):
        """Calling again for the same part adds to (not replaces) the required quantity."""
        requirements = {}
        shortfall.update_part_requirements(self.component, 10, requirements)
        delta = shortfall.update_part_requirements(self.component, 5, requirements)

        data = requirements[self.component.pk]
        self.assertEqual(data['required'], 15)
        self.assertEqual(data['shortfall'], 15)
        # Delta should be the *additional* shortfall introduced by this call
        self.assertEqual(delta, 5)

    def test_delta_is_zero_once_stock_absorbs_shortfall(self):
        """No additional shortfall is reported once available stock/on-order covers the requirement."""
        location = StockLocation.objects.create(name='Location')
        StockItem.objects.create(part=self.component, quantity=100, location=location)

        requirements = {}
        delta = shortfall.update_part_requirements(self.component, 10, requirements)

        self.assertEqual(delta, 0)
        self.assertEqual(requirements[self.component.pk]['shortfall'], 0)

    def test_external_stock_tracked_separately(self):
        """Stock held in an 'external' location is tracked separately, but still counts as available stock."""
        external_location = StockLocation.objects.create(
            name='External', external=True
        )
        internal_location = StockLocation.objects.create(name='Internal')

        StockItem.objects.create(
            part=self.component, quantity=3, location=external_location
        )
        StockItem.objects.create(
            part=self.component, quantity=4, location=internal_location
        )

        requirements = {}
        shortfall.update_part_requirements(self.component, 5, requirements)

        data = requirements[self.component.pk]
        self.assertEqual(data['stock'], 7)
        self.assertEqual(data['external_stock'], 3)


class RecordShortfallParametersTests(ShortfallTestCase):
    """Tests for `record_shortfall_parameters`."""

    def setUp(self):
        super().setUp()
        self.template = ParameterTemplate.objects.create(
            name='Shortfall',
            model_type=ContentType.objects.get_for_model(Part),
        )

    def test_creates_parameter_for_shortfall_part(self):
        """A new Parameter is created for a part with a non-zero shortfall."""
        requirements = {
            self.component.pk: {
                'part': self.component,
                'shortfall': Decimal(15),
            }
        }
        shortfall.record_shortfall_parameters(requirements, self.template.pk)

        param = Parameter.objects.get(
            model_type=ContentType.objects.get_for_model(Part),
            model_id=self.component.pk,
            template=self.template,
        )
        self.assertEqual(param.data, '15')

    def test_updates_existing_parameter(self):
        """An existing Parameter value is updated in-place."""
        Parameter.objects.create(
            model_type=ContentType.objects.get_for_model(Part),
            model_id=self.component.pk,
            template=self.template,
            data='5',
        )

        requirements = {
            self.component.pk: {'part': self.component, 'shortfall': Decimal(25)}
        }
        shortfall.record_shortfall_parameters(requirements, self.template.pk)

        param = Parameter.objects.get(
            model_type=ContentType.objects.get_for_model(Part),
            model_id=self.component.pk,
            template=self.template,
        )
        self.assertEqual(param.data, '25')

    def test_removes_parameter_when_no_longer_in_shortfall(self):
        """An existing Parameter is deleted once the part is no longer in shortfall."""
        Parameter.objects.create(
            model_type=ContentType.objects.get_for_model(Part),
            model_id=self.component.pk,
            template=self.template,
            data='5',
        )

        # No entry for this part in requirements at all - simulates it dropping out of shortfall
        shortfall.record_shortfall_parameters({}, self.template.pk)

        self.assertFalse(
            Parameter.objects.filter(
                model_type=ContentType.objects.get_for_model(Part),
                model_id=self.component.pk,
                template=self.template,
            ).exists()
        )

    def test_zero_shortfall_part_is_skipped(self):
        """A part with zero shortfall does not get a parameter created."""
        requirements = {
            self.component.pk: {'part': self.component, 'shortfall': Decimal(0)}
        }
        shortfall.record_shortfall_parameters(requirements, self.template.pk)

        self.assertFalse(
            Parameter.objects.filter(
                model_type=ContentType.objects.get_for_model(Part),
                model_id=self.component.pk,
                template=self.template,
            ).exists()
        )

    def test_invalid_template_id_does_not_raise(self):
        """An invalid parameter_template_id is handled gracefully (logged, not raised)."""
        requirements = {
            self.component.pk: {'part': self.component, 'shortfall': Decimal(15)}
        }
        # Should not raise
        shortfall.record_shortfall_parameters(requirements, 999999)


class CalculateShortfallTests(ShortfallTestCase):
    """End-to-end tests for `calculate_shortfall`."""

    def setUp(self):
        super().setUp()
        from company.models import Company

        self.customer = Company.objects.create(name='Customer', is_customer=True)

    def make_output(self):
        """Create a DataOutput instance to pass into calculate_shortfall."""
        return DataOutput.objects.create(
            total=0, progress=0, output_type='shortfall_report'
        )

    def test_shortfall_propagates_from_sales_order_to_component(self):
        """A sales order for the assembly propagates required quantity down to its BOM component."""
        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False
        )

        self.assertEqual(requirements[self.assembly.pk]['required'], 10)
        self.assertEqual(requirements[self.assembly.pk]['shortfall'], 10)

        # 10 assemblies * 2 components each = 20 required
        self.assertEqual(requirements[self.component.pk]['required'], 20)
        self.assertEqual(requirements[self.component.pk]['shortfall'], 20)

    def test_stock_absorbs_shortfall_and_stops_propagation(self):
        """Sufficient stock at the assembly level absorbs the shortfall, stopping BOM propagation."""
        location = StockLocation.objects.create(name='Location')
        StockItem.objects.create(part=self.assembly, quantity=10, location=location)

        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False
        )

        self.assertEqual(requirements[self.assembly.pk]['shortfall'], 0)
        # No shortfall at the assembly level - propagation into the BOM should not occur
        self.assertNotIn(self.component.pk, requirements)

    def test_max_bom_depth_limits_propagation(self):
        """Setting max_bom_depth=0 prevents propagation past the top-level parts."""
        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False, max_bom_depth=0
        )

        self.assertIn(self.assembly.pk, requirements)
        self.assertNotIn(self.component.pk, requirements)

    def test_consumable_bom_items_are_excluded(self):
        """BOM items marked as 'consumable' do not propagate shortfall to their sub-part."""
        consumable = Part.objects.create(
            name='Consumable', component=True, purchaseable=True
        )
        consumable.refresh_from_db()
        BomItem.objects.create(
            part=self.assembly, sub_part=consumable, quantity=1, consumable=True
        )

        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False
        )

        self.assertNotIn(consumable.pk, requirements)
        self.assertIn(self.component.pk, requirements)

    def test_category_filter_excludes_non_matching_parts_from_output(self):
        """Category filtering only affects the XLSX export, not the returned requirements dict."""
        from part.models import PartCategory

        category = PartCategory.objects.create(name='Other Category')

        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False, category_id=category.pk
        )

        # The returned dict is unfiltered by category - filtering only applies to the XLSX rows
        self.assertIn(self.assembly.pk, requirements)
        self.assertIn(self.component.pk, requirements)

    def test_generates_output_file(self):
        """A completed DataOutput has an attached xlsx file."""
        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        shortfall.calculate_shortfall(output.pk, hide_no_shortfall=False)

        output.refresh_from_db()
        self.assertTrue(output.complete)
        self.assertTrue(output.output.name.endswith('.xlsx'))

    def test_parameter_template_records_shortfall(self):
        """Passing parameter_template_id writes shortfall values onto parts."""
        template = ParameterTemplate.objects.create(
            name='Shortfall', model_type=ContentType.objects.get_for_model(Part)
        )

        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False, parameter_template_id=template.pk
        )

        param = Parameter.objects.get(
            model_type=ContentType.objects.get_for_model(Part),
            model_id=self.assembly.pk,
            template=template,
        )
        self.assertEqual(param.data, '10')

    def test_missing_data_output_returns_none(self):
        """An invalid output_id is handled gracefully, returning None without raising."""
        result = shortfall.calculate_shortfall(999999)
        self.assertIsNone(result)


class FormatShortfallReportHtmlTests(CalculateShortfallTests):
    """Tests for `format_shortfall_report_html` directly (the scheduled-email body)."""

    def test_hide_no_shortfall_true_omits_zero_shortfall_entries(self):
        """A zero-shortfall part is omitted from the HTML body when hide_no_shortfall=True."""
        location = StockLocation.objects.create(name='Location')
        StockItem.objects.create(part=self.assembly, quantity=1000, location=location)

        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False
        )

        html = shortfall.format_shortfall_report_html(
            requirements, output, hide_no_shortfall=True
        )
        self.assertNotIn('Assembly', html)

    def test_hide_no_shortfall_false_includes_zero_shortfall_entries(self):
        """A zero-shortfall part is included in the HTML body when hide_no_shortfall=False."""
        location = StockLocation.objects.create(name='Location')
        StockItem.objects.create(part=self.assembly, quantity=1000, location=location)

        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False
        )

        html = shortfall.format_shortfall_report_html(
            requirements, output, hide_no_shortfall=False
        )
        self.assertIn('Assembly', html)

    def test_download_link_included_when_output_file_present(self):
        """The email body includes a download link once the DataOutput has a generated file."""
        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False
        )
        output.refresh_from_db()

        html = shortfall.format_shortfall_report_html(
            requirements, output, hide_no_shortfall=False
        )
        self.assertIn('as an Excel file', html)

    def test_download_link_omitted_when_no_output_file(self):
        """The email body omits the download link entirely when the DataOutput has no file."""
        so = SalesOrder.objects.create(customer=self.customer, reference='SO-0001')
        SalesOrderLineItem.objects.create(order=so, part=self.assembly, quantity=10)

        output = self.make_output()
        requirements = shortfall.calculate_shortfall(
            output.pk, hide_no_shortfall=False
        )
        # Use a fresh, never-completed DataOutput - has no attached file
        empty_output = self.make_output()

        html = shortfall.format_shortfall_report_html(
            requirements, empty_output, hide_no_shortfall=False
        )
        self.assertNotIn('as an Excel file', html)
