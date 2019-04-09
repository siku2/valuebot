from typing import Mapping, MutableMapping

__all__ = ["update_map_recursively"]


def update_map_recursively(a: MutableMapping, b: Mapping) -> None:
    """Update a mapping with respect to nested mappings.

    Args:
        a: Mutable mapping to be updated
        b: Mapping to update a with

    Returns:
        Nothing, a is updated in-place.
    """
    for key, b_value in b.items():
        if isinstance(b_value, Mapping):
            try:
                a_value = a[key]
            except KeyError:
                pass
            else:
                if isinstance(a_value, MutableMapping):
                    update_map_recursively(a_value, b_value)
                    continue

        a[key] = b_value
