"""Functions for determining component shortfall."""


def calculate_shortfall(component_id_list: list[int], output_id: int):
    """Calculate the component shortfall for a given list of component IDs.
    
    Arguments:
        component_id_list: List of component IDs to include in the shortfall calculation
        output_id: The ID of the DataOutput (where to save the results)
    """

    print("- calculate shortfall:")
    print("-- part id:", component_id_list)
    print("-- output id:", output_id)
