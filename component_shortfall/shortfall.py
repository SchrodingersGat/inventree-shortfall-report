"""Functions for determining component shortfall.

Process Goals:

For the provided set of parts, we want to detemine a complete list of all sub-components required to build the provided parts.

- For each component we need to iterate down to the bottom of the BOM
- Determine the required quantity of each component
- Determine the available stock of each component
- Determine the shortfall of each component (required - available)

"""

import structlog

import common.models as common_models
import part.models as part_models


logger = structlog.get_logger('inventree.shortfall')


def get_subassemblies(part):
    """Return a list of subassemblies for the provided part."""

    return part.get_bom_items(
        include_virtual=False
    ).filter(consumable=False)


def get_part_requirements(part, requirements: dict, quantity=1):
    """Return requirements for the given part.
    
    Arguments:
        part: The part to process
        quantity: The quantity of the part to process
        requirements: A dict of part requirements (may be updated)

    Returns:
        A dict of part requirements, with the following keys:
        - stock: The available stock of the part
        - on_order: The quantity of the part currently on order
        - building: The quantity of the part currently being built
        - required: The required quantity of the part (for sales order and build orders)
    """

    requirements = requirements or {}

    # TODO
    return {}


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
    required_components : dict = {}

    # A list of components that we need to process
    # Each entry is a tuple of (part, quantity)
    components_to_process = [
        (part, 1) for part in part_models.Part.objects.filter(
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
        part, quantity = components_to_process.pop(0)
        data_output.progress +=1 

        print(".. processing ...", part, quantity)

        # Update every 50 iterations
        if data_output.progress % 50 == 0:
            data_output.save()

        continue

        # TODO: Get the required BOM items for this part

    # TODO: Attach the generated file to the data output

    # Finally, ensure the data output is marked as complete
    data_output.complete = True
    data_output.save()
