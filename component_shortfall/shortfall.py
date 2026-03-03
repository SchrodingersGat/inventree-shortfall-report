"""Functions for determining component shortfall.

Process Goals:

For the provided set of parts, we want to detemine a complete list of all sub-components required to build the provided parts.

- For each component we need to iterate down to the bottom of the BOM
- Determine the required quantity of each component
- Determine the available stock of each component
- Determine the shortfall of each component (required - available)

"""

from decimal import Decimal
import structlog
import tablib

from django.core.files.base import ContentFile

import common.models as common_models
import part.models as part_models


logger = structlog.get_logger('inventree.shortfall')


def get_subassemblies(part):
    """Return a list of subassemblies for the provided part."""

    return part.get_bom_items(
        include_virtual=False
    ).filter(consumable=False)


def update_part_requirements(part, level: int, component_data: dict, additonal_requirements=0, include_variants: bool = False):
    """Return requirements for the given part.
    
    Arguments:
        part: The part to process
        additonal_requirements: The additional quantity required for the part
        component_data: A dict of part requirements (may be updated)

    Returns:
        A dict of part requirements, with the following keys:
        - stock: The available stock of the part
        - on_order: The quantity of the part currently on order
        - building: The quantity of the part currently being built
        - required: The required quantity of the part (for sales order and build orders)
        - allocated: The allocated quantity of the part (for sales order and build orders)
    """

    requirements = component_data.get(part.pk, None) or {}

    # Store the part information against the part
    requirements['part'] = part

    # Fetch (or calculate) the various stock values for this part
    requirements['stock'] = requirements.get('stock', part.get_stock_count(include_variants=False))
    requirements['on_order'] = requirements.get('on_order', part.on_order)
    requirements['allocated'] = requirements.get('allocated', part.allocation_count())
    requirements['building'] = requirements.get('building', part.quantity_being_built)
    requirements['in_production'] = requirements.get('in_production', part.quantity_in_production)
    
    requirements['available'] = requirements['stock'] - requirements['allocated']

    # Calculate latent requirements for this part
    if level == 0:
        requirements['base_requirements'] = requirements.get('base_requirements', part.required_order_quantity())
    else:
        # Ignore base requirements for sub-assemblies
        requirements['base_requirements'] = 0
    

    # Track the total "additional" requirements for this part (based on the parent assembly requirements)
    # The 'additional_requirements' may increase as we process more parent assemblies which require this part as a sub-component
    requirements['additional_requirements'] = requirements.get('additional_requirements', Decimal(0)) + Decimal(additonal_requirements)

    requirements['requirements'] = requirements['base_requirements'] + requirements['additional_requirements']

    # Calculate the "shortfall" for the part
    requirements['shortfall'] = max(
        0,
        requirements['requirements'] - requirements['available'] - requirements['on_order'] - requirements['in_production']
    )

    # Update the global dict of component data
    component_data[part.pk] = requirements


def calculate_shortfall(component_id_list: list[int], output_id: int):
    """Calculate the component shortfall for a given list of component IDs.
    
    Arguments:
        component_id_list: List of component IDs to include in the shortfall calculation
        output_id: The ID of the DataOutput (where to save the results)
    """

    # We keep a track of the required components (based on their ID)
    # Each element in the dict will be a dict with the following keys:
    # - part: The part object
    # - requirements: The required quantity of the part
    component_data : dict = {}

    # A list of components that we need to process
    # Each entry is a tuple of (part, extra_quantity, level)
    components_to_process = [
        (part, 0, 0) for part in part_models.Part.objects.filter(
            pk__in=component_id_list,
            active=True,
            virtual=False,
            )
    ]

    try:
        data_output = common_models.DataOutput.objects.get(pk=output_id)
    except common_models.DataOutput.DoesNotExist:
        logger.error(f"component_shortfall: DataOutput with ID {output_id} does not exist - cannot save results")
        return

    # Update initial conditions for the data output
    data_output.progress = 0
    data_output.total = len(components_to_process)
    data_output.save()

    while components_to_process:
        part, extra_quantity, level = components_to_process.pop(0)
        data_output.progress +=1 

        update_part_requirements(
            part,
            level,
            component_data,
            additonal_requirements=extra_quantity
        )

        shortfall = component_data[part.pk]['shortfall']
        required = component_data[part.pk]['requirements']

        # Update every 50 iterations
        if data_output.progress % 50 == 0:
            data_output.save()

        if shortfall <= 0:
            # No shortfall for this part - skip processing any sub-components
            continue

        if part.assembly:
            components = part.get_bom_items(include_virtual=False).filter(consumable=False).prefetch_related(
                'sub_part',
                'sub_part__category',
            )

            for item in components:
                sub_part = item.sub_part

                # Calculate the quantity multiplier for this sub-part
                required_qty = item.get_required_quantity(shortfall)

                components_to_process.append((sub_part, required_qty, level + 1))
                data_output.total += 1

                print("-", level, "adding sub-part:", sub_part.name, "required qty:", required_qty)

    # Generate the output data file
    headers = [
        'Part ID',
        'Part Name',
        'Part IPN',
        'Category ID',
        'Category Name',
        'Required Quantity',
        'Available Stock',
        'On Order',
        'In Production',
        'Shortfall',
    ]

    dataset = tablib.Dataset(headers=headers)

    for _, data in component_data.items():
        row = [
            data['part'].pk,
            data['part'].name,
            data['part'].IPN,
            data['part'].category.pk if data['part'].category else None,
            data['part'].category.pathstring if data['part'].category else None,
            data['requirements'],
            data['available'],
            data['on_order'],
            data['in_production'],
            data['shortfall'],
        ]
        dataset.append(row)

    # Attach the generated file to the data output
    datafile = dataset.export('csv')

    data_output.mark_complete(
        output=ContentFile(datafile, name='shortfall_report.csv')
    )
