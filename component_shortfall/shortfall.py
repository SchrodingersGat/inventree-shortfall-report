"""Functions for determining component shortfall.

Process Goals:

For the provided set of parts, we want to detemine a complete list of all sub-components required to build the provided parts.

- For each component we need to iterate down to the bottom of the BOM
- Determine the required quantity of each component
- Determine the available stock of each component
- Determine the shortfall of each component (required - available)

"""

import structlog

import part.models as part_models


logger = structlog.get_logger('inventree.shortfall')


def get_subassemblies(part):
    """Return a list of subassemblies for the provided part."""

    return part.get_bom_items(
        include_virtual=False
    ).filter(consumable=False)


def calculate_shortfall(component_id_list: list[int], output_id: int):
    """Calculate the component shortfall for a given list of component IDs.
    
    Arguments:
        component_id_list: List of component IDs to include in the shortfall calculation
        output_id: The ID of the DataOutput (where to save the results)
    """

    # We keep a track of the required components (based on their ID)
    # Each element in the dict will be a dict with the following keys:
    # - part: The part object
    # - required: The required quantity of the part
    required_components : dict = {}

    for component_id in component_id_list:
        try:
            part = part_models.Part.objects.get(pk=component_id)
        except part_models.Part.DoesNotExist:
            logger.warning(f"component_shortfall: Part with ID {component_id} does not exist - skipping")
            continue

    print("PROCESSING COMPLETE")
