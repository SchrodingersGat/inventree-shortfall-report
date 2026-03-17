"""Functions for determining component shortfall.

Process Goals:

- Determine the overall "requirements" - based on outstanding Sales Orders
- Iterate downward through the BOMs for each top-level part, to determine the requirements for each sub-component
- Aggregate the "total" requirements for each component (based on the requirements of all parent assemblies)
- Determine the shortfall for each component, based on the available stock, on-order quantity and in-production quantity

"""

from typing import Optional
from decimal import Decimal
import os
import structlog
import tablib

from django.core.files.base import ContentFile
from django.db.models import F

from InvenTree.helpers_model import construct_absolute_url

import common.models as common_models
import part.models as part_models


logger = structlog.get_logger("inventree.shortfall_report")


def update_part_requirements(
    part, required_qty: Decimal, component_data: dict
) -> Decimal:
    """Return requirements for the given part.

    Arguments:
        part: The part to process
        required_qty: The additional quantity required for the part
        component_data: A dict of part requirements (may be updated)

    Returns:
        The *additional* shortfall for this part (not cumulative)
    """

    requirements = component_data.get(part.pk, None) or {}

    # Store the part information against the part
    requirements["part"] = part

    # Fetch (or calculate) the various stock values for this part
    if "stock" not in requirements:
        requirements["stock"] = part.get_stock_count(include_variants=False)

    # TODO: What about BOM items which allow variants???
    # TODO: What about BOM substitutes?

    # Calculate the total "on order" quantity for this part
    if "on_order" not in requirements:
        requirements["on_order"] = part.on_order

    # Calculate the total "in production" quantity for this part
    if "in_production" not in requirements:
        requirements["in_production"] = part.quantity_being_built

    # Add in the additional requirements
    requirements["required"] = requirements.get("required", Decimal(0)) + Decimal(
        required_qty
    )

    # TODO: Support offset for "in production" quantity

    initial_shortfall = requirements.get("shortfall", Decimal(0))

    # Calculate the "shortfall" for this part
    requirements["shortfall"] = max(
        0, requirements["required"] - requirements["stock"] - requirements["on_order"] - requirements["in_production"]
    )

    # Update the global dict of component data
    component_data[part.pk] = requirements

    # Return the additional shortfall for this part
    return requirements["shortfall"] - initial_shortfall


def get_outstanding_sales_order_parts(category: Optional[part_models.PartCategory] = None) -> dict:
    """Return a dict of outstanding parts (based on open sales orders).

    Returns a dict of part requirements, with the part ID as the key.

    Each element in the dict has the follow values:
    - part: The part object
    - required: The required quantity of the part (for sales order and build orders)

    Arguments:
        - category: Optional category to filter the parts by
    """

    from order.models import SalesOrderLineItem
    from order.status_codes import SalesOrderStatusGroups

    # Find all open sales order line items which are not completed
    sales_order_lines = SalesOrderLineItem.objects.filter(
        order__status__in=SalesOrderStatusGroups.OPEN,
        part__virtual=False,
        shipped__lt=F("quantity"),
    ).prefetch_related(
        "part",
    )

    # TODO: Filter by order status (e.g. exclude pending orders)

    # TODO: Filter by order date (e.g. only include orders which are due within a certain time frame)

    # Filter by part category (e.g. only include orders for parts within a certain category)
    if category:
        categories = category.get_descendants(include_self=True)
        sales_order_lines = sales_order_lines.filter(part__category__in=categories)

    outstanding_parts = {}

    for line in sales_order_lines:
        deficit = max(0, line.quantity - line.shipped)

        if deficit <= 0:
            # No outstanding quantity for this line item
            continue

        part_data = outstanding_parts.get(line.part.pk, None) or {
            "part": line.part,
            "required": Decimal(0),
        }
        part_data["required"] += deficit
        outstanding_parts[line.part.pk] = part_data

    return outstanding_parts


def get_outstanding_build_order_parts(category: Optional[part_models.PartCategory] = None) -> dict:
    """Return a dict of outstanding parts (based on open build orders).

    Returns a dict of part requirements, with the part ID as the key.

    Each element in the dict has the follow values:
    - part: The part object
    - required: The required quantity of the part (for sales order and build orders)

    Arguments:
        - category: Optional category to filter the parts by
    """

    from build.models import BuildLine
    from build.status_codes import BuildStatusGroups

    # Find all open build order line items which are not completed
    # Here we are interested in the "deficit" quantity for each line item
    # i.e. the quantity which is still required to complete the build order
    # We must take into account the quantity already consumed against this line item
    build_order_lines = BuildLine.objects.filter(
        build__status__in=BuildStatusGroups.ACTIVE_CODES,
        build__part__virtual=False,
        consumed__lt=F("quantity"),
    ).prefetch_related(
        "bom_item__sub_part",
    )

    # Filter by part category (e.g. only include orders for parts within a certain category)
    if category:
        categories = category.get_descendants(include_self=True)
        build_order_lines = build_order_lines.filter(
            build__part__category__in=categories
        )

    outstanding_parts = {}

    for line in build_order_lines:
        deficit = max(0, line.quantity - line.consumed)

        if deficit <= 0:
            # No outstanding quantity for this line item
            continue

        part = line.bom_item.sub_part

        part_data = outstanding_parts.get(part.pk, None) or {
            "part": part,
            "required": Decimal(0),
        }
        part_data["required"] += deficit
        outstanding_parts[part.pk] = part_data

    return outstanding_parts


def get_outstanding_parts(category: Optional[part_models.PartCategory] = None) -> dict:
    """Return a dict of outstanding parts (based on open sales orders and build orders)."""

    # Start with the outstanding sales order parts
    outstanding_parts = {}
    
    so_parts = get_outstanding_sales_order_parts(category=category)
    bo_parts = get_outstanding_build_order_parts(category=category)

    def add_part_info(parts):
        for part_id, part_data in parts.items():
            if part_id in outstanding_parts:
                outstanding_parts[part_id]["required"] += part_data["required"]
            else:
                outstanding_parts[part_id] = part_data

    add_part_info(so_parts)
    add_part_info(bo_parts)

    return outstanding_parts


def calculate_shortfall(
    output_id: int, category_id: Optional[int] = None, max_bom_depth: int = 50
) -> dict:
    """Calculate the component shortfall for a given list of component IDs.

    Arguments:
        output_id: The ID of the DataOutput (where to save the results)
        max_bom_depth: The maximum depth to traverse the BOM when calculating shortfall (default: 50)
        category_id: The ID of the category to filter parts by (optional)

    Returns:
        A dict of part requirements, with the part ID as the key.

        Each element in the dict has the follow values:
        - part: The part object
        - required: The required quantity of the part (for sales order and build orders)
        - stock: The current stock on hand for this part
        - on_order: The quantity of this part currently on order
        - shortfall: The calculated shortfall for this part (required - stock - on_order)
    """

    logger.info("Generating component shortfall report")

    try:
        data_output = common_models.DataOutput.objects.get(pk=output_id)
    except common_models.DataOutput.DoesNotExist:
        logger.error(
            f"component_shortfall: DataOutput with ID {output_id} does not exist - cannot save results"
        )
        return

    try:
        if category_id:
            category = part_models.PartCategory.objects.get(pk=category_id)
        else:
            category = None
    except (ValueError, part_models.PartCategory.DoesNotExist):
        logger.warning(
            f"component_shortfall: PartCategory with ID {category_id} does not exist - cannot filter parts"
        )
        category = None

    # First, determine the set of components which are "on order"
    initial_parts = get_outstanding_parts(category=category)

    # Let's keep track of all the requirements, top-to-bottom, in a single dict - keyed by part ID
    # key: part ID
    # - part: Part instance
    # - required: Total required quantity for this part (cumulative)
    # - stock: Current stock on hand for this part
    # - on_order: Quantity of this part currently on order
    # - building: Quantity of this part currently being built
    requirements = {}

    # Keep a list of the components still required to process - start with the initial set of outstanding parts
    # Each entry is a tuple of (part, quantity, level)
    components_to_process = []

    # Start with the initial set of outstanding parts
    for _, data in initial_parts.items():
        part = data["part"]
        required_qty = data["required"]

        components_to_process.append((part, required_qty, 0))

    # Update initial conditions for the data output
    data_output.progress = 0
    data_output.total = len(components_to_process)
    data_output.save()

    while components_to_process:
        part, quantity, level = components_to_process.pop(0)
        data_output.progress += 1

        shortfall = update_part_requirements(part, quantity, requirements)

        # Update every 50 iterations
        if data_output.progress % 50 == 0:
            data_output.save()

        if shortfall <= 0:
            # No shortfall for this part - skip processing any sub-components
            continue

        # Prevent deep recursion into the BOM - if we have reached the maximum level, then we will not process any sub-components
        if level >= max_bom_depth:
            continue

        # Is this an assembly?
        if part.assembly:
            components = (
                part.get_bom_items(include_virtual=False)
                .filter(consumable=False)
                .prefetch_related(
                    "sub_part",
                    "sub_part__category",
                )
            )

            for item in components:
                sub_part = item.sub_part

                # Calculate the quantity multiplier for this sub-part
                required_qty = item.get_required_quantity(shortfall)

                components_to_process.append((sub_part, required_qty, level + 1))
                data_output.total += 1

    # Generate the output data file
    headers = [
        "Part ID",
        "Part Name",
        "Part IPN",
        "Category ID",
        "Category Name",
        "Current Stock",
        "On Order",
        "In Production",
        "Required Quantity",
        "Shortfall",
        "Units",
    ]

    dataset = tablib.Dataset(headers=headers)

    for _, data in requirements.items():
        part = data["part"]
        url = construct_absolute_url(part.get_absolute_url())

        row = [
            f'=HYPERLINK("{url}", "{part.pk}")',
            part.name,
            part.IPN,
            part.category.pk if part.category else None,
            part.category.pathstring if part.category else None,
            Decimal(data["stock"]),
            Decimal(data["on_order"]),
            Decimal(data["in_production"]),
            Decimal(data["required"]),
            Decimal(data["shortfall"]),
            part.units,
        ]
        dataset.append(row)

    # Attach the generated file to the data output
    datafile = dataset.export("xlsx")

    data_output.mark_complete(
        output=ContentFile(datafile, name="shortfall_report.xlsx")
    )

    return requirements


def format_shortfall_report_html(
    requirements: dict, output: common_models.DataOutput, hide_no_shortfall: bool = True
) -> str:
    """Format the shortfall report as a HTML document."""

    from django.template import Template, Context

    file_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "component_shortfall",
        "shortfall_email.html",
    )

    with open(file_path, "r") as f:
        template_content = f.read()

    context_data = {}

    # Add download link
    if output and output.output:
        context_data["download_link"] = construct_absolute_url(output.output.url)

    # Add all the requirements entries
    requirements_list = []

    for entry in requirements.values():
        if hide_no_shortfall and entry.get("shortfall", 0) <= 0:
            continue

        requirements_list.append({
            **entry,
            "part_url": construct_absolute_url(entry["part"].get_absolute_url()),
        })

    context_data["requirements"] = requirements_list

    template = Template(template_content)
    context = Context(context_data)

    data = template.render(context)

    return data
