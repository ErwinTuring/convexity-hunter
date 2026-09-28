import datetime
import unittest

from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.host_grounder_run_input import (
    HostGrounderRunInput,
    HostGrounderRunInputBounds,
    HostGrounderSubquestion,
    validate_host_context_binding,
    validate_ordered_coverage_ids,
)


_BOUNDS = HostGrounderRunInputBounds(
    max_run_input_bytes=10_000,
    max_string_bytes=1_000,
    max_array_items=20,
)


def _input(*, run_id="run-golden-7", event_date=datetime.date(2026, 9, 29)):
    user_input = UserEventInput(
        description="事件 Café",
        provisional_symbols=("ACME", "ACME"),
        source_locators=("https://example.test/a", "untrusted hint"),
        event_date=event_date,
    )
    subquestions = (
        HostGrounderSubquestion("sq-α", "核对归因"),
        HostGrounderSubquestion("sq-β", "发布日期与事件日分离"),
    )
    return HostGrounderRunInput(run_id, user_input, subquestions, _BOUNDS)


class HostGrounderRunInputTests(unittest.TestCase):
    def test_literal_canonical_bytes_and_sha256_golden(self):
        run_input = _input()
        expected = (
            '{"mode":"event","schema_version":"host-grounder-run-input-v0.1",'
            '"subquestions":[{"subquestion_id":"sq-α","text":"核对归因"},'
            '{"subquestion_id":"sq-β","text":"发布日期与事件日分离"}],'
            '"user_input":{"description":"事件 Café","event_date":"2026-09-29",'
            '"provisional_symbols":["ACME","ACME"],'
            '"source_locators":["https://example.test/a","untrusted hint"]}}'
        )
        self.assertEqual(run_input.canonical_json, expected)
        self.assertEqual(run_input.canonical_bytes, expected.encode("utf-8"))
        self.assertEqual(
            run_input.canonical_input_hash,
            "6f93be73a22f2a2980c4bf393830658ce4380c574399359d1a7d695925094bf6",
        )

    def test_literal_null_date_golden_and_run_id_is_outside_hash(self):
        run_input = _input(event_date=None)
        expected = (
            '{"mode":"event","schema_version":"host-grounder-run-input-v0.1",'
            '"subquestions":[{"subquestion_id":"sq-α","text":"核对归因"},'
            '{"subquestion_id":"sq-β","text":"发布日期与事件日分离"}],'
            '"user_input":{"description":"事件 Café","event_date":null,'
            '"provisional_symbols":["ACME","ACME"],'
            '"source_locators":["https://example.test/a","untrusted hint"]}}'
        )
        self.assertEqual(run_input.canonical_json, expected)
        self.assertEqual(
            run_input.canonical_input_hash,
            "33c052afeedcb71ed79a897d86f20d4fd2d4b2ce956cfbff042e5189cda4df5a",
        )
        self.assertEqual(_input(run_id="run-different", event_date=None).canonical_input_hash,
                         run_input.canonical_input_hash)

    def test_exact_input_identity_order_and_source_locator_are_preserved(self):
        run_input = _input()
        original = run_input.user_input
        rebuilt = HostGrounderRunInput(
            run_input.run_id, original, run_input.subquestions, _BOUNDS
        )
        self.assertIs(rebuilt.user_input, original)
        self.assertEqual(run_input.subquestion_ids, ("sq-α", "sq-β"))
        self.assertIn('"source_locators":["https://example.test/a","untrusted hint"]',
                      run_input.canonical_json)
        reversed_plan = HostGrounderRunInput(
            run_input.run_id,
            run_input.user_input,
            tuple(reversed(run_input.subquestions)),
            _BOUNDS,
        )
        self.assertNotEqual(reversed_plan.canonical_input_hash, run_input.canonical_input_hash)

    def test_context_binding_checks_run_identity_object_identity_and_hash(self):
        run_input = _input()
        validate_host_context_binding(
            run_input,
            context_run_id=run_input.run_id,
            context_raw_input=run_input.user_input,
            context_canonical_input_hash=run_input.canonical_input_hash,
        )
        with self.assertRaisesRegex(ValueError, "run_id"):
            validate_host_context_binding(
                run_input,
                context_run_id="other-run",
                context_raw_input=run_input.user_input,
                context_canonical_input_hash=run_input.canonical_input_hash,
            )
        equal_but_distinct = UserEventInput(
            run_input.user_input.description,
            run_input.user_input.provisional_symbols,
            run_input.user_input.source_locators,
            run_input.user_input.event_date,
        )
        with self.assertRaisesRegex(ValueError, "object"):
            validate_host_context_binding(
                run_input,
                context_run_id=run_input.run_id,
                context_raw_input=equal_but_distinct,
                context_canonical_input_hash=run_input.canonical_input_hash,
            )
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_host_context_binding(
                run_input,
                context_run_id=run_input.run_id,
                context_raw_input=run_input.user_input,
                context_canonical_input_hash="0" * 64,
            )

    def test_ordered_coverage_ids_require_exact_complete_plan(self):
        run_input = _input()
        validate_ordered_coverage_ids(run_input, ("sq-α", "sq-β"))
        for ids in (
            ("sq-β", "sq-α"),
            ("sq-α",),
            ("sq-α", "sq-β", "extra"),
            ("sq-α", "sq-α"),
        ):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                validate_ordered_coverage_ids(run_input, ids)
        with self.assertRaises(TypeError):
            validate_ordered_coverage_ids(run_input, ["sq-α", "sq-β"])

    def test_empty_duplicate_and_wrongly_typed_subquestions_reject(self):
        user_input = _input().user_input
        cases = (
            (),
            (HostGrounderSubquestion("same", "first"),
             HostGrounderSubquestion("same", "second")),
            ("id/text pair",),
        )
        for subquestions in cases:
            with self.subTest(subquestions=subquestions), self.assertRaises((TypeError, ValueError)):
                HostGrounderRunInput("run", user_input, subquestions, _BOUNDS)
        for subquestion_id, text in (("", "text"), ("id", "")):
            with self.subTest(subquestion_id=subquestion_id, text=text):
                with self.assertRaises(ValueError):
                    HostGrounderSubquestion(subquestion_id, text)
        with self.assertRaises(TypeError):
            HostGrounderRunInput("run", object(), (HostGrounderSubquestion("id", "text"),), _BOUNDS)

    def test_host_bounds_are_explicit_positive_integers_and_fail_closed(self):
        for kwargs in (
            {"max_run_input_bytes": True, "max_string_bytes": 20, "max_array_items": 2},
            {"max_run_input_bytes": 0, "max_string_bytes": 20, "max_array_items": 2},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                HostGrounderRunInputBounds(**kwargs)

        user_input = _input().user_input
        questions = _input().subquestions
        with self.assertRaisesRegex(ValueError, "max_string_bytes"):
            HostGrounderRunInput(
                "run", user_input, questions,
                HostGrounderRunInputBounds(10_000, 4, 20),
            )
        with self.assertRaisesRegex(ValueError, "max_array_items"):
            HostGrounderRunInput(
                "run", user_input, questions,
                HostGrounderRunInputBounds(10_000, 1_000, 1),
            )
        with self.assertRaisesRegex(ValueError, "max_run_input_bytes"):
            HostGrounderRunInput(
                "run", user_input, questions,
                HostGrounderRunInputBounds(20, 1_000, 20),
            )

    def test_no_coercion_of_run_id_subquestion_sequence_or_bounds(self):
        user_input = _input().user_input
        question = (HostGrounderSubquestion("id", "text"),)
        with self.assertRaises(ValueError):
            HostGrounderRunInput(7, user_input, question, _BOUNDS)
        with self.assertRaises(TypeError):
            HostGrounderRunInput("run", user_input, list(question), _BOUNDS)
        with self.assertRaises(TypeError):
            HostGrounderRunInput("run", user_input, question, object())


if __name__ == "__main__":
    unittest.main()
