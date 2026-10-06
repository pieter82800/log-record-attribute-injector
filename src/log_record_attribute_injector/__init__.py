"""Public package interface for log_record_attribute_injector.

Only AttributeInjectorFilter is exported. Keeping the surface to a single name
prevents accidental coupling between callers and internal helpers.
"""

from .core import AttributeInjectorFilter
from .core import AttributeSource

__all__ = ["AttributeInjectorFilter", "AttributeSource"]
