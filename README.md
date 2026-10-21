# Log Record Attribute Injector

A `logging.Filter` subclass that attaches predefined attributes (such as
`request_id` and `hostname`) to every `LogRecord` before it reaches handlers,
so formatters and structured-log exporters can rely on those fields being
present.

## Usage

```python
import logging, socket
from log_record_attribute_injector import AttributeInjectorFilter

def context():
    # In a real app this reads from a request-local or process state.
    return {"hostname": socket.gethostname(), "request_id": get_current_request_id()}

handler = logging.StreamHandler()
handler.addFilter(AttributeInjectorFilter("app", context))
handler.setFormatter(logging.Formatter("%(request_id)s %(hostname)s %(message)s"))

logger = logging.getLogger("app")
logger.addHandler(handler)
logger.info("started")
```

Exported names: `AttributeInjectorFilter`, `AttributeSource`.

## Why this exists

Structured logging only works if every record carries the context you need to
correlate it. The stdlib gives you `logging.LoggerAdapter` and `extra=...`, but
both require the caller of `logger.info(...)` to remember to pass context every
time. A filter sits in one place on the handler and guarantees the attribute is
there for the formatter, regardless of which call site produced the record.

The trade-off: attributes are sourced from a callable invoked on every record.
That is a function call per log line. If your source does real work (reads from
a lock-protected context var, for example), that cost is paid in the logging
path. The alternative — snapshotting once at construction — cannot reflect a
changing request id, which defeats the purpose.

## Edges you will hit

* **Existing attributes are not overwritten.** If a `LoggerAdapter` or an
  earlier filter has already set `request_id` on the record, the injector
  leaves it alone. Closest producer wins. If you want forced overwrite, set
  the attribute before the record reaches this filter, or write your own
  filter — this one is deliberately conservative.
* **A faulty source is swallowed.** If your context callable raises, the
  record is still emitted, just without the injected attributes. Logging must
  not die because a context store is broken. You will see the attribute
  absent from the formatted line rather than a traceback at the log call.
* **No name-based routing.** Despite extending `logging.Filter`, this filter
  always returns `True`. The `name` argument only affects where you can
  attach it via `logger.addFilter`; it does not reject records by logger name.
  Routing is the handlers' job.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

## Contributing

Issues and pull requests are welcome. Please keep the dependency list empty —
that constraint is the point of the project, not an oversight.

