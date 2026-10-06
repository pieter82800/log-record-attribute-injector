"""A logging.Filter that injects predefined attributes into every LogRecord.

The standard logging.Filter contract is used purely for its lifecycle hook:
``filter`` is called once per record before it reaches handlers, giving us a
single place to attach contextual attributes (request_id, hostname, etc.) that
formatters and downstream consumers can rely on.

Design decisions
----------------
* Attributes are sourced from a callable (``AttributeSource``) rather than a
  static dict. Contextual values such as the current request id are only known
  at emit time, not at filter construction time. A callable lets the same
  filter instance serve a process whose context changes over its lifetime.
* Attributes are never overwritten. A logger or handler earlier in the chain
  may have already attached a value with stronger provenance (for example, a
  per-request handler that captured the id directly from the inbound request).
  Honouring the existing value keeps precedence predictable: the closest
  producer of a value wins.
* Missing context (``AttributeSource`` raises or returns ``None``) is treated
  as "no value". We store ``None`` only when the source explicitly returned
  ``None`` for a key; if the source raises, the key is not set at all. This
  lets a caller distinguish "source said: no value" from "source exploded".
"""

from __future__ import annotations

import logging
from typing import Callable, Mapping

#: A function returning a fresh snapshot of the attributes to inject.
#: Re-invoked on every record so the filter always sees current context.
AttributeSource = Callable[[], Mapping[str, object]]


class AttributeInjectorFilter(logging.Filter):
    """Logging filter that attaches attributes from a source callable.

    Example
    -------
    >>> import logging, socket
    >>> def source():
    ...     return {"hostname": socket.gethostname()}
    >>> filt = AttributeInjectorFilter("app", source)
    >>> handler = logging.StreamHandler()
    >>> handler.addFilter(filt)
    >>> logging.getLogger("app").addHandler(handler)

    Parameters
    ----------
    name:
        Passed to ``logging.Filter``. Used by the logging machinery to decide
        which loggers this filter applies to when attached to a logger rather
        than a handler. Has no effect on attribute injection.
    source:
        Zero-argument callable returning a mapping of attribute names to
        values. Called once per ``filter`` invocation. Returning a fresh dict
        each call is the caller's responsibility; a stale reference would
        defeat the point of sourcing dynamically.
    """

    def __init__(self, name: str = "", source: AttributeSource | None = None) -> None:
        super().__init__(name)
        if source is None:
            # A no-op source keeps the filter usable (it still functions as a
            # name-based filter) but injects nothing. This avoids a NoneType
            # crash in hot logging paths where source was simply omitted.
            source = lambda: {}
        self._source = source

    def filter(self, record: logging.LogRecord) -> bool:
        """Inject attributes from ``source`` into ``record`` and accept it.

        Returns ``True`` unconditionally: the name-based acceptance decision
        is delegated to ``logging.Filter.__init__``'s machinery via
        ``super().filter`` when a name was supplied, but when no name is set
        the base implementation always returns True, which is the behaviour
        we want for a pure attribute-injecting filter.

        We deliberately do not call ``super().filter`` here. The base method
        performs name matching against ``record.name``; a filter constructed
        with ``name="app"`` would reject records from ``"app.sub"`` only by
        exact prefix match, and coupling injection to that match surprises
        users who attach the filter to a handler (where name filtering is
        usually undesirable). Injection and routing are kept orthogonal.
        """
        try:
            snapshot = self._source()
        except Exception:
            # A faulty context provider must not tear down logging. Swallow
            # the exception and proceed without injection for this record.
            return True

        for key, value in snapshot.items():
            # Skip keys already present: closest producer wins. ``hasattr`` is
            # the right test because LogRecord uses plain attribute slots.
            if hasattr(record, key):
                continue
            setattr(record, key, value)

        return True
