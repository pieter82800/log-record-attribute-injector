import logging
import unittest

from log_record_attribute_injector import AttributeInjectorFilter


def _make_record(name="test", msg="hello", args=()):
    return logging.LogRecord(
        name=name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


class AttributeInjectorFilterTest(unittest.TestCase):
    def test_injects_attributes_from_source(self):
        source = lambda: {"request_id": "abc-123", "hostname": "worker-1"}
        f = AttributeInjectorFilter("app", source)

        record = _make_record()
        self.assertTrue(f.filter(record))

        self.assertEqual(record.request_id, "abc-123")
        self.assertEqual(record.hostname, "worker-1")

    def test_source_is_called_fresh_each_record(self):
        calls = []

        def source():
            calls.append(1)
            return {"request_id": "id-" + str(len(calls))}

        f = AttributeInjectorFilter(source=source)

        r1 = _make_record()
        r2 = _make_record()
        f.filter(r1)
        f.filter(r2)

        self.assertEqual(calls, [1, 1])
        self.assertEqual(r1.request_id, "id-1")
        self.assertEqual(r2.request_id, "id-2")

    def test_existing_attribute_is_not_overwritten(self):
        source = lambda: {"request_id": "injected", "hostname": "injected"}
        f = AttributeInjectorFilter(source=source)

        record = _make_record()
        record.request_id = "already-here"

        self.assertTrue(f.filter(record))
        self.assertEqual(record.request_id, "already-here")
        self.assertEqual(record.hostname, "injected")

    def test_source_returning_empty_mapping_is_noop(self):
        f = AttributeInjectorFilter(source=lambda: {})
        record = _make_record()
        self.assertTrue(f.filter(record))
        self.assertFalse(hasattr(record, "request_id"))

    def test_source_returning_none_value_sets_attribute_to_none(self):
        f = AttributeInjectorFilter(source=lambda: {"request_id": None})
        record = _make_record()
        self.assertTrue(f.filter(record))
        self.assertTrue(hasattr(record, "request_id"))
        self.assertIsNone(record.request_id)

    def test_source_raising_is_swallowed(self):
        def bad_source():
            raise RuntimeError("context store unavailable")

        f = AttributeInjectorFilter(source=bad_source)
        record = _make_record()

        # Must not raise.
        self.assertTrue(f.filter(record))

        # Nothing was injected.
        self.assertFalse(hasattr(record, "request_id"))

    def test_default_source_when_omitted_injects_nothing(self):
        f = AttributeInjectorFilter("app")
        record = _make_record()
        self.assertTrue(f.filter(record))
        self.assertFalse(hasattr(record, "request_id"))

    def test_filter_returns_true_regardless_of_name(self):
        # A filter named "app" must still accept a record named "other",
        # because we deliberately decouple injection from name-based routing.
        f = AttributeInjectorFilter("app", source=lambda: {"k": "v"})
        record = _make_record(name="other")
        self.assertTrue(f.filter(record))
        self.assertEqual(record.k, "v")

    def test_works_with_real_logging_handler(self):
        captured = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                captured.append(record)

        source = lambda: {"request_id": "real-1"}
        handler = CapturingHandler()
        handler.addFilter(AttributeInjectorFilter(source=source))

        logger = logging.getLogger("test.real")
        logger.handlers = [handler]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        logger.info("hello")

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].request_id, "real-1")
        self.assertEqual(captured[0].getMessage(), "hello")

    def test_injected_attribute_usable_in_format(self):
        source = lambda: {"request_id": "fmt-1"}
        f = AttributeInjectorFilter(source=source)
        record = _make_record()
        f.filter(record)

        # The standard %(<attr>)s format spec reads attributes via getattr,
        # so an injected attribute is available to any formatter that names it.
        formatter = logging.Formatter("%(request_id)s %(message)s")
        self.assertEqual(formatter.format(record), "fmt-1 hello")


if __name__ == "__main__":
    unittest.main()
