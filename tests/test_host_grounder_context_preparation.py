import datetime
import copy
import hashlib
import inspect
import json
import unittest
from dataclasses import replace
from types import MappingProxyType, SimpleNamespace
from unittest.mock import Mock, patch

from convexity_hunter import host_grounder_builder as builder_module
from convexity_hunter import host_grounder_runtime as runtime_module
from convexity_hunter import host_grounder_evidence_catalog as catalog_module
from convexity_hunter.event_intelligence import MethodologizedDateRange
from convexity_hunter.host_grounder_evidence_catalog import (
    HostEvidenceCatalogAuditHolder,
    parse_grounder_output_v0_3,
)
from convexity_hunter.host_grounder_runtime import (
    DISCOVERY_SYSTEM_PROMPT_V0_5,
    SEMANTIC_SYSTEM_PROMPT_V0_5,
    HostGrounderRuntimeError,
    run_host_grounder_same_run_evidence_catalog_v0_1,
    run_host_grounder_same_run_evidence_catalog_v0_2,
    run_host_grounder_same_run_evidence_catalog_v0_3,
)
from convexity_hunter.market_data import UnderlyingKey, UnderlyingSecurityType
from tests.test_host_grounder_evidence_catalog import (
    _FakeClient,
    _canonical,
    _catalog_for,
    _fixture,
    _runtime as _legacy_runtime,
    _wire_envelope,
    _wire_bundle,
    _wire_verdict,
    _catalog_for,
)


_DYNAMIC_CLAIM_ID = "claim-from-this-run-17"
_DYNAMIC_HYPOTHESIS_ID = "hypothesis-from-this-run-23"


def _dynamic_payload(run_input, context):
    catalog = _catalog_for(run_input, context)
    producer = _wire_envelope(run_input, catalog, claim_id=_DYNAMIC_CLAIM_ID)
    hypothesis = producer["hypotheses"][0]
    hypothesis["hypothesis_id"] = _DYNAMIC_HYPOTHESIS_ID
    hypothesis["supporting_claim_ids"] = [_DYNAMIC_CLAIM_ID]
    producer["coverage"][0]["claim_ids"] = [_DYNAMIC_CLAIM_ID]
    envelope, envelope_bytes = parse_grounder_output_v0_3(
        _canonical(producer),
        100_000,
        max_string_bytes=run_input.bounds.max_string_bytes,
        max_array_items=run_input.bounds.max_array_items,
        run_id=run_input.run_id,
        canonical_input_hash=run_input.canonical_input_hash,
        source_bodies=context.source_bodies,
        catalog=catalog,
    )
    verdict = _wire_verdict(run_input, context, catalog, envelope, envelope_bytes)
    verdict["hypotheses"][0]["hypothesis_id"] = _DYNAMIC_HYPOTHESIS_ID
    return producer, verdict


class HostGrounderContextPreparationTests(unittest.TestCase):
    def setUp(self):
        self.run_input, base_context = _fixture()
        self.context = replace(
            base_context,
            event_description_binding=None,
            underlying_bindings={},
        )
        self.producer, self.verdict = _dynamic_payload(self.run_input, self.context)

    def _invoke(self, preparer, *, context=None, producer=None, verdict=None):
        calls = []
        discovery = _FakeClient("discovery", _canonical(producer or self.producer), calls)
        semantic = _FakeClient("semantic", _canonical(verdict or self.verdict), calls)
        holder = HostEvidenceCatalogAuditHolder(
            run_id=self.run_input.run_id,
            canonical_input_hash=self.run_input.canonical_input_hash,
        )
        result = run_host_grounder_same_run_evidence_catalog_v0_2(
            self.run_input,
            context or self.context,
            discovery_client=discovery,
            semantic_client=semantic,
            audit_holder=holder,
            max_json_bytes=100_000,
            max_source_body_bytes=20_000,
            max_catalog_entries=100,
            max_catalog_bytes=100_000,
            max_catalog_paragraphs=100,
            host_context_preparer=preparer,
        )
        return result, calls

    def _parse_producer(self, producer):
        catalog = _catalog_for(self.run_input, self.context)
        envelope, envelope_bytes = parse_grounder_output_v0_3(
            _canonical(producer),
            100_000,
            max_string_bytes=self.run_input.bounds.max_string_bytes,
            max_array_items=self.run_input.bounds.max_array_items,
            run_id=self.run_input.run_id,
            canonical_input_hash=self.run_input.canonical_input_hash,
            source_bodies=self.context.source_bodies,
            catalog=catalog,
        )
        verdict = _wire_verdict(
            self.run_input, self.context, catalog, envelope, envelope_bytes
        )
        verdict["hypotheses"] = verdict["hypotheses"][:len(producer["hypotheses"])]
        for index, hypothesis in enumerate(verdict["hypotheses"]):
            hypothesis["hypothesis_id"] = producer["hypotheses"][index]["hypothesis_id"]
        return verdict

    def test_v03_adds_one_runtime_callable_without_changing_frozen_signatures(self):
        runtime_functions = {
            name for name, value in vars(runtime_module).items()
            if name.startswith("run_host_grounder") and inspect.isfunction(value)
        }
        self.assertEqual(
            runtime_functions,
            {
                "run_host_grounder_same_run",
                "run_host_grounder_same_run_quote_localization_v0_1",
                "run_host_grounder_same_run_evidence_catalog_v0_1",
                "run_host_grounder_same_run_evidence_catalog_v0_2",
                "run_host_grounder_same_run_evidence_catalog_v0_3",
            },
        )
        self.assertFalse(hasattr(runtime_module, "__all__"))

        v01_parameters = tuple(
            inspect.signature(run_host_grounder_same_run_evidence_catalog_v0_1).parameters.values()
        )
        v02_signature = inspect.signature(run_host_grounder_same_run_evidence_catalog_v0_2)
        v03_signature = inspect.signature(run_host_grounder_same_run_evidence_catalog_v0_3)
        expected_v01_names = (
            "run_input", "context", "discovery_client", "semantic_client", "audit_holder",
            "max_json_bytes", "max_source_body_bytes", "max_catalog_entries",
            "max_catalog_bytes", "max_catalog_paragraphs",
        )
        expected_v02_names = expected_v01_names + ("host_context_preparer",)
        self.assertEqual(tuple(parameter.name for parameter in v01_parameters), expected_v01_names)
        self.assertEqual(tuple(v02_signature.parameters), expected_v02_names)
        self.assertEqual(v03_signature, v02_signature)
        self.assertEqual(len(v03_signature.parameters), 11)
        for parameter in v01_parameters[:2]:
            self.assertIs(parameter.kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for parameter in v01_parameters[2:]:
            self.assertIs(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(v02_signature.parameters["host_context_preparer"].default, None)

    def test_producer_diagnostic_constructor_keeps_closed_versioned_pairs(self):
        old_checks = (
            "producer_wire_normalization",
            "producer_run_stage_binding",
            "producer_coverage_order",
            "producer_binding_extraction",
        )
        fine_checks = (
            "producer_v0_3_wire_decode",
            "producer_v0_3_root_shape",
            "producer_v0_3_catalog_source_validation",
            "producer_v0_3_claims_catalog_expansion",
            "producer_v0_3_bindings_catalog_expansion",
            "producer_v0_3_canonical_size",
            "producer_v0_3_internal_v0_1_schema",
            "producer_v0_3_recanonicalization",
        )
        for check in old_checks + fine_checks:
            error = HostGrounderRuntimeError(
                "PRODUCER_ENVELOPE_INVALID",
                failure_stage="producer_envelope_normalization",
                failure_check=check,
            )
            self.assertEqual(error.failure_check, check)
        for code, stage, check in (
            ("OTHER", "producer_envelope_normalization", fine_checks[0]),
            ("PRODUCER_ENVELOPE_INVALID", "semantic_wire_parse", fine_checks[0]),
            ("PRODUCER_ENVELOPE_INVALID", "producer_envelope_normalization", "unknown"),
            ("PRODUCER_ENVELOPE_INVALID", None, fine_checks[0]),
        ):
            with self.subTest(code=code, stage=stage, check=check), self.assertRaises(ValueError):
                HostGrounderRuntimeError(code, failure_stage=stage, failure_check=check)

        semantic_checks = (
            "wire_decode", "topshape", "run_binding", "catalog_validation",
            "producer_binding_alignment", "evidence_ref_expansion",
            "internal_verdict_validation",
        )
        for check in semantic_checks:
            HostGrounderRuntimeError(
                "SEMANTIC_VERDICT_REJECTED",
                failure_stage="semantic_wire_parse",
                failure_check=check,
            )

    def test_v03_success_keeps_preparer_prompt_and_normalized_bytes(self):
        catalog = _catalog_for(self.run_input, self.context)
        _, expected_normalized_bytes = parse_grounder_output_v0_3(
            _canonical(self.producer),
            100_000,
            max_string_bytes=self.run_input.bounds.max_string_bytes,
            max_array_items=self.run_input.bounds.max_array_items,
            run_id=self.run_input.run_id,
            canonical_input_hash=self.run_input.canonical_input_hash,
            source_bodies=self.context.source_bodies,
            catalog=catalog,
        )
        calls = []
        result = run_host_grounder_same_run_evidence_catalog_v0_3(
            self.run_input,
            self.context,
            discovery_client=_FakeClient("discovery", _canonical(self.producer), calls),
            semantic_client=_FakeClient("semantic", _canonical(self.verdict), calls),
            audit_holder=HostEvidenceCatalogAuditHolder(
                run_id=self.run_input.run_id,
                canonical_input_hash=self.run_input.canonical_input_hash,
            ),
            max_json_bytes=100_000,
            max_source_body_bytes=20_000,
            max_catalog_entries=100,
            max_catalog_bytes=100_000,
            max_catalog_paragraphs=100,
            host_context_preparer=lambda snapshot, receipt, original: original,
        )
        sidecar = json.loads(result.audit.sidecar_utf8)
        self.assertEqual(result.audit.normalized_envelope_utf8, expected_normalized_bytes)
        self.assertEqual(
            sidecar["producer_prompt_version"], "host-grounder-discovery-prompt-v0.5"
        )
        self.assertEqual([call[0] for call in calls], ["discovery", "semantic"])

    def test_v02_dispatches_and_audits_v05_without_changing_other_versions(self):
        result, calls = self._invoke(lambda snapshot, receipt, original: original)
        sidecar = json.loads(result.audit.sidecar_utf8)
        self.assertEqual([call[0] for call in calls], ["discovery", "semantic"])
        self.assertEqual(calls[0][1], DISCOVERY_SYSTEM_PROMPT_V0_5)
        self.assertEqual(calls[1][1], SEMANTIC_SYSTEM_PROMPT_V0_5)
        self.assertEqual(sidecar["producer_prompt_version"], "host-grounder-discovery-prompt-v0.5")
        self.assertEqual(sidecar["schema_version"], "host-grounder-quote-localization-audit-v0.3")
        self.assertEqual(
            set(sidecar),
            {
                "schema_version", "run_id", "canonical_input_hash", "producer_wire_version",
                "producer_prompt_version", "producer_content_sha256", "normalized_envelope_sha256",
                "source_body_hashes", "verifier_wire_version", "validator_version",
                "localizer_version", "catalog_schema_version", "catalog_generator_version",
                "catalog_sha256",
            },
        )
        self.assertEqual(sidecar["producer_wire_version"], "grounder-output-v0.3")
        self.assertEqual(sidecar["verifier_wire_version"], "semantic-verdict-v0.3")
        self.assertEqual(sidecar["validator_version"], "host-grounder-semantic-verifier-prompt-v0.5")
        self.assertEqual(
            result.build_result.semantic_validation.receipt["schema_version"],
            "semantic-validation-v0.2",
        )
        self.assertEqual(len(calls), 2)

    def test_producer_diagnostics_preserve_valid_normalized_bytes_and_audit(self):
        catalog = _catalog_for(self.run_input, self.context)
        _, expected_normalized_bytes = parse_grounder_output_v0_3(
            _canonical(self.producer),
            100_000,
            max_string_bytes=self.run_input.bounds.max_string_bytes,
            max_array_items=self.run_input.bounds.max_array_items,
            run_id=self.run_input.run_id,
            canonical_input_hash=self.run_input.canonical_input_hash,
            source_bodies=self.context.source_bodies,
            catalog=catalog,
        )

        result, calls = self._invoke(lambda snapshot, receipt, original: original)
        sidecar = json.loads(result.audit.sidecar_utf8)
        producer_bytes = _canonical(self.producer).encode("utf-8")
        self.assertEqual(result.audit.normalized_envelope_utf8, expected_normalized_bytes)
        self.assertEqual(result.audit.producer_content_utf8, producer_bytes)
        self.assertEqual(
            sidecar["normalized_envelope_sha256"],
            hashlib.sha256(expected_normalized_bytes).hexdigest(),
        )
        self.assertEqual(sidecar["producer_content_sha256"], hashlib.sha256(producer_bytes).hexdigest())
        self.assertEqual([call[0] for call in calls], ["discovery", "semantic"])

    def test_producer_normalization_failure_checks_are_closed_and_fail_early(self):
        catalog = _catalog_for(self.run_input, self.context)
        parsed_envelope, normalized_bytes = parse_grounder_output_v0_3(
            _canonical(self.producer),
            100_000,
            max_string_bytes=self.run_input.bounds.max_string_bytes,
            max_array_items=self.run_input.bounds.max_array_items,
            run_id=self.run_input.run_id,
            canonical_input_hash=self.run_input.canonical_input_hash,
            source_bodies=self.context.source_bodies,
            catalog=catalog,
        )
        wrong_binding = dict(parsed_envelope)
        wrong_binding["request_id"] = "other-run"
        runtime_json = SimpleNamespace(
            dumps=json.dumps,
            loads=Mock(side_effect=ValueError("PRIVATE_DIAGNOSTIC_SENTINEL")),
        )
        injections = (
            (
                "producer_wire_normalization",
                lambda: patch.object(
                    runtime_module,
                    "parse_grounder_output_v0_3",
                    side_effect=ValueError("PRIVATE_DIAGNOSTIC_SENTINEL"),
                ),
            ),
            (
                "producer_run_stage_binding",
                lambda: patch.object(
                    runtime_module,
                    "parse_grounder_output_v0_3",
                    return_value=(wrong_binding, normalized_bytes),
                ),
            ),
            (
                "producer_coverage_order",
                lambda: patch.object(
                    runtime_module,
                    "validate_ordered_coverage_ids",
                    side_effect=ValueError("PRIVATE_DIAGNOSTIC_SENTINEL"),
                ),
            ),
            (
                "producer_wire_normalization",
                lambda: patch.object(
                    runtime_module,
                    "parse_grounder_output_v0_3",
                    return_value=(parsed_envelope, object()),
                ),
            ),
            (
                "producer_binding_extraction",
                lambda: patch.object(runtime_module, "json", runtime_json),
            ),
        )
        for check, make_injection in injections:
            preparer = Mock()
            calls = []
            discovery = _FakeClient("discovery", _canonical(self.producer), calls)
            semantic = _FakeClient("semantic", _canonical(self.verdict), calls)
            with self.subTest(check=check), make_injection(), patch.object(
                runtime_module, "_build_host_grounder_v0_2"
            ) as builder:
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    run_host_grounder_same_run_evidence_catalog_v0_2(
                        self.run_input,
                        self.context,
                        discovery_client=discovery,
                        semantic_client=semantic,
                        audit_holder=HostEvidenceCatalogAuditHolder(
                            run_id=self.run_input.run_id,
                            canonical_input_hash=self.run_input.canonical_input_hash,
                        ),
                        max_json_bytes=100_000,
                        max_source_body_bytes=20_000,
                        max_catalog_entries=100,
                        max_catalog_bytes=100_000,
                        max_catalog_paragraphs=100,
                        host_context_preparer=preparer,
                    )
            error = raised.exception
            self.assertEqual(error.code, "PRODUCER_ENVELOPE_INVALID")
            self.assertEqual(error.failure_stage, "producer_envelope_normalization")
            self.assertEqual(error.failure_check, check)
            self.assertEqual(error.args, ("PRODUCER_ENVELOPE_INVALID",))
            self.assertEqual(str(error), "PRODUCER_ENVELOPE_INVALID")
            self.assertEqual(
                repr(error),
                "HostGrounderRuntimeError(code='PRODUCER_ENVELOPE_INVALID')",
            )
            self.assertIsNone(error.__cause__)
            self.assertTrue(error.__suppress_context__)
            self.assertNotIn("PRIVATE_DIAGNOSTIC_SENTINEL", str(error) + repr(error))
            self.assertEqual([call[0] for call in calls], ["discovery"])
            preparer.assert_not_called()
            builder.assert_not_called()

    def test_v03_parser_failures_surface_only_the_eight_closed_checks_and_stop_early(self):
        fine_checks = (
            "producer_v0_3_wire_decode",
            "producer_v0_3_root_shape",
            "producer_v0_3_catalog_source_validation",
            "producer_v0_3_claims_catalog_expansion",
            "producer_v0_3_bindings_catalog_expansion",
            "producer_v0_3_canonical_size",
            "producer_v0_3_internal_v0_1_schema",
            "producer_v0_3_recanonicalization",
        )
        for check in fine_checks:
            calls = []
            discovery = _FakeClient("discovery", _canonical(self.producer), calls)
            semantic = _FakeClient("semantic", _canonical(self.verdict), calls)
            preparer = Mock()

            def fail_at_closed_check(*args, progress, **kwargs):
                progress(check)
                raise ValueError("PRIVATE_DIAGNOSTIC_SENTINEL")

            with self.subTest(check=check), patch.object(
                runtime_module,
                "_parse_grounder_output_v0_3_with_progress",
                side_effect=fail_at_closed_check,
            ), patch.object(runtime_module, "_build_host_grounder_v0_2") as builder:
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    run_host_grounder_same_run_evidence_catalog_v0_3(
                        self.run_input,
                        self.context,
                        discovery_client=discovery,
                        semantic_client=semantic,
                        audit_holder=HostEvidenceCatalogAuditHolder(
                            run_id=self.run_input.run_id,
                            canonical_input_hash=self.run_input.canonical_input_hash,
                        ),
                        max_json_bytes=100_000,
                        max_source_body_bytes=20_000,
                        max_catalog_entries=100,
                        max_catalog_bytes=100_000,
                        max_catalog_paragraphs=100,
                        host_context_preparer=preparer,
                    )
            error = raised.exception
            self.assertEqual(error.code, "PRODUCER_ENVELOPE_INVALID")
            self.assertEqual(error.failure_stage, "producer_envelope_normalization")
            self.assertEqual(error.failure_check, check)
            self.assertEqual(error.args, ("PRODUCER_ENVELOPE_INVALID",))
            self.assertEqual(str(error), "PRODUCER_ENVELOPE_INVALID")
            self.assertEqual(
                repr(error),
                "HostGrounderRuntimeError(code='PRODUCER_ENVELOPE_INVALID')",
            )
            self.assertNotIn("PRIVATE_DIAGNOSTIC_SENTINEL", str(error) + repr(error))
            self.assertIsNone(error.__cause__)
            self.assertTrue(error.__suppress_context__)
            self.assertEqual([call[0] for call in calls], ["discovery"])
            preparer.assert_not_called()
            builder.assert_not_called()

    def test_catalog_v01_producer_errors_keep_null_diagnostics(self):
        calls = []
        discovery = _FakeClient("discovery", "not-json", calls)
        semantic = _FakeClient("semantic", _canonical(self.verdict), calls)
        with self.assertRaises(HostGrounderRuntimeError) as raised:
            run_host_grounder_same_run_evidence_catalog_v0_1(
                self.run_input,
                self.context,
                discovery_client=discovery,
                semantic_client=semantic,
                audit_holder=HostEvidenceCatalogAuditHolder(
                    run_id=self.run_input.run_id,
                    canonical_input_hash=self.run_input.canonical_input_hash,
                ),
                max_json_bytes=100_000,
                max_source_body_bytes=20_000,
                max_catalog_entries=100,
                max_catalog_bytes=100_000,
                max_catalog_paragraphs=100,
            )
        self.assertEqual(raised.exception.code, "PRODUCER_ENVELOPE_INVALID")
        self.assertIsNone(raised.exception.failure_stage)
        self.assertIsNone(raised.exception.failure_check)
        self.assertEqual([call[0] for call in calls], ["discovery"])

    def test_nonnull_consumed_field_without_verified_binding_is_not_projected(self):
        producer = copy.deepcopy(self.producer)
        producer["field_bindings"] = [
            item
            for item in producer["field_bindings"]
            if item["field_path"] != "/hypotheses/0/distribution_hypothesis"
        ]
        verdict = self._parse_producer(producer)

        result, calls = self._invoke(
            lambda snapshot, receipt, original: original,
            producer=producer,
            verdict=verdict,
        )
        diagnostics = result.build_result.diagnostics
        self.assertEqual(len(calls), 2)
        self.assertIsNone(result.build_result.submission)
        self.assertTrue(
            any(
                item.code == "HYPOTHESIS_REJECTED_BY_VALIDATOR"
                and "required field binding is not supported" in item.reason
                for item in diagnostics
            )
        )

    def test_bound_but_unresolved_and_omitted_hypotheses_are_never_auto_supported(self):
        unresolved_verdict = copy.deepcopy(self.verdict)
        unresolved_verdict["hypotheses"][0]["outcome"] = "unresolved"
        unresolved_verdict["hypotheses"][0]["evidence_refs"] = []
        for binding in unresolved_verdict["field_bindings"]:
            binding["outcome"] = "unresolved"
            binding["evidence_refs"] = []

        bound_result, bound_calls = self._invoke(
            lambda snapshot, receipt, original: original,
            verdict=unresolved_verdict,
        )
        self.assertEqual(len(bound_calls), 2)
        self.assertEqual(
            bound_result.build_result.semantic_validation.receipt[
                "verified_hypothesis_ids"
            ],
            (),
        )
        self.assertIsNone(bound_result.build_result.submission)

        omitted_producer = copy.deepcopy(self.producer)
        omitted_producer["hypotheses"] = []
        omitted_producer["field_bindings"] = []
        omitted_verdict = self._parse_producer(omitted_producer)
        omitted_verdict["hypotheses"] = []
        omitted_verdict["field_bindings"] = []
        omitted_result, omitted_calls = self._invoke(
            lambda snapshot, receipt, original: original,
            producer=omitted_producer,
            verdict=omitted_verdict,
        )
        self.assertEqual(len(omitted_calls), 2)
        self.assertEqual(
            omitted_result.build_result.semantic_validation.receipt[
                "verified_hypothesis_ids"
            ],
            (),
        )
        self.assertIsNone(omitted_result.build_result.submission)

    def test_unapproved_producer_prompt_version_fails_before_calls(self):
        calls = []
        with self.assertRaises(HostGrounderRuntimeError) as raised:
            runtime_module._run_host_grounder_same_run_evidence_catalog(
                self.run_input,
                self.context,
                discovery_client=_FakeClient("discovery", _canonical(self.producer), calls),
                semantic_client=_FakeClient("semantic", _canonical(self.verdict), calls),
                audit_holder=HostEvidenceCatalogAuditHolder(
                    run_id=self.run_input.run_id,
                    canonical_input_hash=self.run_input.canonical_input_hash,
                ),
                max_json_bytes=100_000,
                max_source_body_bytes=20_000,
                max_catalog_entries=100,
                max_catalog_bytes=100_000,
                max_catalog_paragraphs=100,
                producer_prompt_version="host-grounder-discovery-prompt-v0.6",
            )
        self.assertEqual(raised.exception.code, "DISCOVERY_PROMPT_VERSION_INVALID")
        self.assertEqual(calls, [])

    def test_discovery_client_cannot_rewrite_the_pinned_prompt_version(self):
        for corrupted_version in (
            "host-grounder-discovery-prompt-v0.4",
            "host-grounder-discovery-prompt-v0.6",
            True,
        ):
            with self.subTest(corrupted_version=corrupted_version):
                calls = []
                holder = HostEvidenceCatalogAuditHolder(
                    run_id=self.run_input.run_id,
                    canonical_input_hash=self.run_input.canonical_input_hash,
                )

                class MutatingDiscovery(_FakeClient):
                    def complete(client_self, system_prompt, source_prompt):
                        receipt = super(MutatingDiscovery, client_self).complete(
                            system_prompt, source_prompt
                        )
                        object.__setattr__(
                            holder, "_producer_prompt_version", corrupted_version
                        )
                        return receipt

                discovery = MutatingDiscovery(
                    "discovery", _canonical(self.producer), calls
                )
                semantic = _FakeClient("semantic", _canonical(self.verdict), calls)
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    run_host_grounder_same_run_evidence_catalog_v0_2(
                        self.run_input,
                        self.context,
                        discovery_client=discovery,
                        semantic_client=semantic,
                        audit_holder=holder,
                        max_json_bytes=100_000,
                        max_source_body_bytes=20_000,
                        max_catalog_entries=100,
                        max_catalog_bytes=100_000,
                        max_catalog_paragraphs=100,
                        host_context_preparer=lambda snapshot, receipt, original: original,
                    )

                self.assertEqual(raised.exception.code, "AUDIT_RETENTION_FAILED")
                self.assertEqual([entry[0] for entry in calls], ["discovery"])
                self.assertFalse(holder.finalized)

    def test_validated_snapshot_dynamic_ids_fill_only_absent_context(self):
        reference = object()
        key = UnderlyingKey("ACME", "XNAS", UnderlyingSecurityType.EQUITY, "USD")
        events = []
        runtime_validator = runtime_module.validate_semantic_validation_receipt
        builder_validator = builder_module.validate_semantic_validation_receipt

        def runtime_validate(*args, **kwargs):
            events.append("runtime-validate")
            return runtime_validator(*args, **kwargs)

        def builder_validate(*args, **kwargs):
            events.append("builder-validate")
            return builder_validator(*args, **kwargs)

        def prepare(snapshot, receipt, original):
            events.append("prepare")
            self.assertIsInstance(receipt, MappingProxyType)
            self.assertIs(type(receipt["source_body_hashes"]), tuple)
            self.assertIn(_DYNAMIC_CLAIM_ID, receipt["verified_claim_ids"])
            with self.assertRaises(TypeError):
                receipt["run_id"] = "changed"
            decoded = json.loads(snapshot.canonical_bytes.decode("utf-8"))
            self.assertEqual(decoded["claims"][0]["claim_id"], _DYNAMIC_CLAIM_ID)
            self.assertEqual(
                decoded["hypotheses"][0]["hypothesis_id"], _DYNAMIC_HYPOTHESIS_ID
            )
            return replace(
                original,
                event_description_binding=_DYNAMIC_CLAIM_ID,
                underlying_bindings={
                    (_DYNAMIC_HYPOTHESIS_ID, "ACME"): (key, reference)
                },
            )

        with patch.object(
            runtime_module,
            "validate_semantic_validation_receipt",
            side_effect=runtime_validate,
        ), patch.object(
            builder_module,
            "validate_semantic_validation_receipt",
            side_effect=builder_validate,
        ):
            result, calls = self._invoke(prepare)

        self.assertEqual(
            events,
            ["runtime-validate", "prepare", "runtime-validate", "builder-validate"],
        )
        self.assertEqual([entry[0] for entry in calls], ["discovery", "semantic"])
        self.assertEqual(
            result.build_result.context.event_description_binding, _DYNAMIC_CLAIM_ID
        )
        submission = result.build_result.submission
        self.assertIsNotNone(submission)
        self.assertEqual(submission.event_description, "ACME filed a report.")
        self.assertEqual(
            submission.hypotheses[0].hypothesis_id, _DYNAMIC_HYPOTHESIS_ID
        )
        self.assertIs(submission.hypotheses[0].underlying_key, key)

    def test_missing_preparer_fails_before_any_model_call(self):
        calls = []
        discovery = _FakeClient("discovery", _canonical(self.producer), calls)
        semantic = _FakeClient("semantic", _canonical(self.verdict), calls)
        with self.assertRaises(HostGrounderRuntimeError) as raised:
            run_host_grounder_same_run_evidence_catalog_v0_2(
                self.run_input,
                self.context,
                discovery_client=discovery,
                semantic_client=semantic,
                audit_holder=HostEvidenceCatalogAuditHolder(
                    run_id=self.run_input.run_id,
                    canonical_input_hash=self.run_input.canonical_input_hash,
                ),
                max_json_bytes=100_000,
                max_source_body_bytes=20_000,
                max_catalog_entries=100,
                max_catalog_bytes=100_000,
                max_catalog_paragraphs=100,
                host_context_preparer=None,
            )
        self.assertEqual(raised.exception.code, "HOST_CONTEXT_PREPARER_INVALID")
        self.assertEqual(calls, [])

    def test_invalid_receipt_stops_before_preparer(self):
        calls = []
        discovery = _FakeClient("discovery", _canonical(self.producer), calls)
        semantic = _FakeClient("semantic", _canonical(self.verdict), calls)
        invoked = []

        def reject_receipt(*args, **kwargs):
            raise ValueError("private validation detail")

        with patch.object(
            runtime_module,
            "validate_semantic_validation_receipt",
            side_effect=reject_receipt,
        ):
            with self.assertRaises(HostGrounderRuntimeError) as raised:
                run_host_grounder_same_run_evidence_catalog_v0_2(
                    self.run_input,
                    self.context,
                    discovery_client=discovery,
                    semantic_client=semantic,
                    audit_holder=HostEvidenceCatalogAuditHolder(
                        run_id=self.run_input.run_id,
                        canonical_input_hash=self.run_input.canonical_input_hash,
                    ),
                    max_json_bytes=100_000,
                    max_source_body_bytes=20_000,
                    max_catalog_entries=100,
                    max_catalog_bytes=100_000,
                    max_catalog_paragraphs=100,
                    host_context_preparer=lambda *args: invoked.append(args),
                )
        self.assertEqual(raised.exception.code, "SEMANTIC_VERDICT_REJECTED")
        self.assertEqual(invoked, [])
        self.assertEqual([entry[0] for entry in calls], ["discovery", "semantic"])
        self.assertNotIn("private validation detail", str(raised.exception))

    def test_failure_stages_identify_only_the_three_v0_2_operations(self):
        for operation, stage in (
            ("_parse_semantic_verdict_v0_3", "semantic_wire_parse"),
            ("build_semantic_validation_receipt", "semantic_receipt_construction"),
            ("validate_semantic_validation_receipt", "semantic_receipt_validation"),
        ):
            preparer = Mock()
            with self.subTest(stage=stage), patch.object(
                runtime_module, operation,
                side_effect=ValueError("PRIVATE_DIAGNOSTIC_SENTINEL"),
            ), patch.object(runtime_module, "_build_host_grounder_v0_2") as builder:
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    self._invoke(preparer)
            error = raised.exception
            self.assertEqual(error.failure_stage, stage)
            self.assertIsNone(error.failure_check)
            self.assertEqual(error.code, "SEMANTIC_VERDICT_REJECTED")
            self.assertEqual(error.args, ("SEMANTIC_VERDICT_REJECTED",))
            self.assertEqual(str(error), "SEMANTIC_VERDICT_REJECTED")
            self.assertEqual(
                repr(error),
                "HostGrounderRuntimeError(code='SEMANTIC_VERDICT_REJECTED')",
            )
            self.assertIsNone(error.__cause__)
            self.assertTrue(error.__suppress_context__)
            self.assertNotIn("PRIVATE_DIAGNOSTIC_SENTINEL", str(error) + repr(error))
            preparer.assert_not_called()
            builder.assert_not_called()

    def test_failure_stage_accepts_only_closed_values_with_static_rejection(self):
        for stage in (
            None,
            "semantic_wire_parse",
            "semantic_receipt_construction",
            "semantic_receipt_validation",
        ):
            with self.subTest(stage=stage):
                error = HostGrounderRuntimeError("CODE", failure_stage=stage)
                self.assertEqual(error.failure_stage, stage)
                self.assertEqual(error.args, ("CODE",))
                self.assertEqual(str(error), "CODE")
                self.assertEqual(repr(error), "HostGrounderRuntimeError(code='CODE')")
        for stage in ("PRIVATE_DIAGNOSTIC_SENTINEL", "", 1, True, [], {}, object()):
            with self.subTest(stage_type=type(stage).__name__):
                with self.assertRaises(ValueError) as raised:
                    HostGrounderRuntimeError("CODE", failure_stage=stage)
                self.assertEqual(str(raised.exception), "invalid failure_stage")
                self.assertNotIn("PRIVATE_DIAGNOSTIC_SENTINEL", repr(raised.exception))
        for code, check in (
            ("CODE", "producer_wire_normalization"),
            ("PRODUCER_ENVELOPE_INVALID", None),
            ("PRODUCER_ENVELOPE_INVALID", "PRIVATE_DIAGNOSTIC_SENTINEL"),
        ):
            with self.subTest(producer_code=code, producer_check=check):
                with self.assertRaises(ValueError) as raised:
                    HostGrounderRuntimeError(
                        code,
                        failure_stage="producer_envelope_normalization",
                        failure_check=check,
                    )
                if check == "PRIVATE_DIAGNOSTIC_SENTINEL":
                    self.assertEqual(str(raised.exception), "invalid failure_stage")
                    self.assertNotIn("PRIVATE_DIAGNOSTIC_SENTINEL", repr(raised.exception))

    def test_legacy_catalog_semantic_errors_keep_none_stage_and_representations(self):
        self.assertIsNone(HostGrounderRuntimeError("CODE").failure_stage)
        for operation in (
            "parse_semantic_verdict_v0_3", "build_semantic_validation_receipt"
        ):
            with self.subTest(operation=operation), patch.object(
                runtime_module, operation,
                side_effect=ValueError("PRIVATE_DIAGNOSTIC_SENTINEL"),
            ), patch.object(runtime_module, "_build_host_grounder_v0_2") as builder:
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    _legacy_runtime(
                        self.run_input, self.context, self.producer, self.verdict
                    )
            error = raised.exception
            self.assertIsNone(error.failure_stage)
            self.assertIsNone(error.failure_check)
            self.assertEqual(error.code, "SEMANTIC_VERDICT_REJECTED")
            self.assertEqual(error.args, ("SEMANTIC_VERDICT_REJECTED",))
            self.assertEqual(str(error), "SEMANTIC_VERDICT_REJECTED")
            self.assertEqual(
                repr(error),
                "HostGrounderRuntimeError(code='SEMANTIC_VERDICT_REJECTED')",
            )
            self.assertIsNone(error.__cause__)
            self.assertTrue(error.__suppress_context__)
            builder.assert_not_called()

    def test_parser_check_categories_stop_before_preparer_and_builder(self):
        real_parser = catalog_module._parse_semantic_verdict_v0_3
        for check in (
            "wire_decode", "topshape", "run_binding", "catalog_validation",
            "producer_binding_alignment", "evidence_ref_expansion",
            "internal_verdict_validation",
        ):
            def reject(raw, cap, **options):
                wire = json.loads(raw)
                if check == "wire_decode":
                    raw = "PRIVATE_DIAGNOSTIC_SENTINEL"
                elif check == "topshape":
                    wire["extra"] = "PRIVATE_DIAGNOSTIC_SENTINEL"
                elif check == "run_binding":
                    wire["run_id"] = "PRIVATE_DIAGNOSTIC_SENTINEL"
                elif check == "catalog_validation":
                    options["source_bodies"] = {}
                elif check == "producer_binding_alignment":
                    options["producer_binding_evidence_ids"] = []
                elif check == "evidence_ref_expansion":
                    wire["claims"][0]["evidence_refs"][0]["evidence_id"] = "PRIVATE_DIAGNOSTIC_SENTINEL"
                else:
                    wire["claims"][0]["rationale"] = None
                if check != "wire_decode":
                    raw = _canonical(wire)
                return real_parser(raw, cap, **options)

            preparer = Mock()
            with self.subTest(check=check), patch.object(
                runtime_module, "_parse_semantic_verdict_v0_3", side_effect=reject,
            ), patch.object(runtime_module, "_build_host_grounder_v0_2") as builder:
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    self._invoke(preparer)
            error = raised.exception
            self.assertEqual(error.failure_check, check)
            self.assertEqual(error.failure_stage, "semantic_wire_parse")
            self.assertEqual(error.args, ("SEMANTIC_VERDICT_REJECTED",))
            self.assertEqual(str(error), "SEMANTIC_VERDICT_REJECTED")
            self.assertEqual(repr(error), "HostGrounderRuntimeError(code='SEMANTIC_VERDICT_REJECTED')")
            self.assertIsNone(error.__cause__)
            self.assertTrue(error.__suppress_context__)
            self.assertNotIn("PRIVATE_DIAGNOSTIC_SENTINEL", str(error) + repr(error))
            preparer.assert_not_called()
            builder.assert_not_called()

    def test_public_and_diagnostic_parser_bytes_and_first_failure_are_identical(self):
        run, context = _fixture()
        catalog, producer, _, _, wire = _wire_bundle(run, context)
        options = dict(
            max_string_bytes=run.bounds.max_string_bytes,
            max_array_items=run.bounds.max_array_items,
            run_id=run.run_id, canonical_input_hash=run.canonical_input_hash,
            source_bodies=context.source_bodies, catalog=catalog,
            producer_binding_evidence_ids=tuple(x["evidence_id"] for x in producer["field_bindings"]),
        )
        for outcome in ("supported", "contradicted", "unresolved"):
            value = copy.deepcopy(wire)
            value["claims"][0]["outcome"] = outcome
            if outcome == "unresolved":
                value["claims"][0]["evidence_refs"] = []
            raw = _canonical(value)
            progress = catalog_module._SemanticVerdictProgress()
            self.assertEqual(
                catalog_module.parse_semantic_verdict_v0_3(raw, 100_000, **options),
                catalog_module._parse_semantic_verdict_v0_3(raw, 100_000, progress=progress, **options),
            )
        value = copy.deepcopy(wire)
        value["extra"] = True
        value["run_id"] = "wrong-run"
        value["claims"][0]["evidence_refs"][0]["evidence_id"] = "unknown"
        for expected in ("topshape", "run_binding", "evidence_ref_expansion"):
            progress = catalog_module._SemanticVerdictProgress()
            with self.assertRaises(ValueError) as public:
                catalog_module.parse_semantic_verdict_v0_3(_canonical(value), 100_000, **options)
            with self.assertRaises(ValueError) as diagnostic:
                catalog_module._parse_semantic_verdict_v0_3(_canonical(value), 100_000, progress=progress, **options)
            self.assertEqual(type(public.exception), type(diagnostic.exception))
            self.assertEqual(public.exception.args, diagnostic.exception.args)
            self.assertEqual(progress.failure_check, expected)
            if expected == "topshape":
                del value["extra"]
            elif expected == "run_binding":
                value["run_id"] = run.run_id

    def test_failure_check_is_closed_and_requires_wire_parse_stage(self):
        checks = (
            "wire_decode", "topshape", "run_binding", "catalog_validation",
            "producer_binding_alignment", "evidence_ref_expansion",
            "internal_verdict_validation",
        )
        for check in checks:
            error = HostGrounderRuntimeError("CODE", failure_stage="semantic_wire_parse", failure_check=check)
            self.assertEqual(error.failure_check, check)
            self.assertEqual(error.args, ("CODE",))
            self.assertEqual(repr(error), "HostGrounderRuntimeError(code='CODE')")
            for stage in (None, "semantic_receipt_construction", "semantic_receipt_validation"):
                with self.assertRaisesRegex(ValueError, "^invalid failure_check$"):
                    HostGrounderRuntimeError("CODE", failure_stage=stage, failure_check=check)
        for check in ("PRIVATE_DIAGNOSTIC_SENTINEL", "", True, 1, [], {}, object()):
            with self.assertRaisesRegex(ValueError, "^invalid failure_check$"):
                HostGrounderRuntimeError("CODE", failure_stage="semantic_wire_parse", failure_check=check)
        self.assertIsNone(HostGrounderRuntimeError("CODE").failure_check)

        producer_checks = (
            "producer_wire_normalization",
            "producer_run_stage_binding",
            "producer_coverage_order",
            "producer_binding_extraction",
        )
        for check in producer_checks:
            error = HostGrounderRuntimeError(
                "PRODUCER_ENVELOPE_INVALID",
                failure_stage="producer_envelope_normalization",
                failure_check=check,
            )
            self.assertEqual(error.failure_stage, "producer_envelope_normalization")
            self.assertEqual(error.failure_check, check)
            self.assertEqual(error.args, ("PRODUCER_ENVELOPE_INVALID",))
            self.assertEqual(
                repr(error),
                "HostGrounderRuntimeError(code='PRODUCER_ENVELOPE_INVALID')",
            )
            for stage in (None, "semantic_wire_parse", "semantic_receipt_construction", "semantic_receipt_validation"):
                with self.assertRaises(ValueError):
                    HostGrounderRuntimeError(
                        "PRODUCER_ENVELOPE_INVALID",
                        failure_stage=stage,
                        failure_check=check,
                    )
        for check in (
            "wire_decode",
            "topshape",
            "run_binding",
            "catalog_validation",
            "producer_binding_alignment",
            "evidence_ref_expansion",
            "internal_verdict_validation",
        ):
            with self.assertRaises(ValueError):
                HostGrounderRuntimeError(
                    "PRODUCER_ENVELOPE_INVALID",
                    failure_stage="producer_envelope_normalization",
                    failure_check=check,
                )
        with self.assertRaisesRegex(ValueError, "^invalid failure_check$") as raised:
            HostGrounderRuntimeError(
                "PRODUCER_ENVELOPE_INVALID",
                failure_stage="semantic_wire_parse",
                failure_check="PRIVATE_DIAGNOSTIC_SENTINEL",
            )
        self.assertNotIn("PRIVATE_DIAGNOSTIC_SENTINEL", str(raised.exception))

    def test_snapshot_and_source_mutations_are_sanitized_and_stop_builder(self):
        callbacks = (
            lambda snapshot, receipt, original: (
                object.__setattr__(snapshot, "envelope_hash", "0" * 64) or original
            ),
            lambda snapshot, receipt, original: (
                object.__setattr__(
                    original.source_bodies["source-1"], "title", "mutated"
                )
                or original
            ),
        )
        for callback in callbacks:
            calls = []
            discovery = _FakeClient("discovery", _canonical(self.producer), calls)
            semantic = _FakeClient("semantic", _canonical(self.verdict), calls)
            with patch.object(runtime_module, "_build_host_grounder_v0_2") as builder:
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    run_host_grounder_same_run_evidence_catalog_v0_2(
                        self.run_input,
                        self.context,
                        discovery_client=discovery,
                        semantic_client=semantic,
                        audit_holder=HostEvidenceCatalogAuditHolder(
                            run_id=self.run_input.run_id,
                            canonical_input_hash=self.run_input.canonical_input_hash,
                        ),
                        max_json_bytes=100_000,
                        max_source_body_bytes=20_000,
                        max_catalog_entries=100,
                        max_catalog_bytes=100_000,
                        max_catalog_paragraphs=100,
                        host_context_preparer=callback,
                    )
            self.assertEqual(raised.exception.code, "HOST_CONTEXT_PREPARATION_REJECTED")
            self.assertEqual([entry[0] for entry in calls], ["discovery", "semantic"])
            builder.assert_not_called()

    def test_unknown_hypothesis_id_cannot_add_host_binding(self):
        key = UnderlyingKey("ACME", "XNAS", UnderlyingSecurityType.EQUITY, "USD")

        def prepare(snapshot, receipt, original):
            return replace(
                original,
                underlying_bindings={("unknown-hypothesis", "ACME"): (key, object())},
            )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            self._invoke(prepare)
        self.assertEqual(raised.exception.code, "HOST_CONTEXT_PREPARATION_REJECTED")

    def test_unverified_underlying_entity_binding_cannot_add_host_binding(self):
        key = UnderlyingKey("ACME", "XNAS", UnderlyingSecurityType.EQUITY, "USD")
        rejected_entity_verdict = json.loads(_canonical(self.verdict))
        rejected_entity_verdict["field_bindings"][0]["outcome"] = "unresolved"
        rejected_entity_verdict["field_bindings"][0]["evidence_refs"] = []

        def prepare(snapshot, receipt, original):
            return replace(
                original,
                underlying_bindings={
                    (_DYNAMIC_HYPOTHESIS_ID, "ACME"): (key, object())
                },
            )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            self._invoke(prepare, verdict=rejected_entity_verdict)
        self.assertEqual(raised.exception.code, "HOST_CONTEXT_PREPARATION_REJECTED")

    def test_reconstructed_context_rejects_postconstruction_invalid_key(self):
        key = UnderlyingKey("ACME", "XNAS", UnderlyingSecurityType.EQUITY, "USD")

        def prepare(snapshot, receipt, original):
            prepared = replace(
                original,
                underlying_bindings={
                    (_DYNAMIC_HYPOTHESIS_ID, "ACME"): (key, object())
                },
            )
            object.__setattr__(key, "currency", "")
            return prepared

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            self._invoke(prepare)
        self.assertEqual(raised.exception.code, "HOST_CONTEXT_PREPARATION_REJECTED")

    def test_reconstructed_context_freezes_callback_mutable_mappings(self):
        key = UnderlyingKey("ACME", "XNAS", UnderlyingSecurityType.EQUITY, "USD")
        reference = object()

        def prepare(snapshot, receipt, original):
            prepared = replace(
                original,
                event_description_binding=_DYNAMIC_CLAIM_ID,
                underlying_bindings={
                    (_DYNAMIC_HYPOTHESIS_ID, "ACME"): (key, reference)
                },
            )
            object.__setattr__(prepared, "source_bodies", dict(prepared.source_bodies))
            object.__setattr__(
                prepared,
                "underlying_bindings",
                dict(prepared.underlying_bindings),
            )
            return prepared

        result, _ = self._invoke(prepare)
        prepared = result.build_result.context
        self.assertIsInstance(prepared.source_bodies, MappingProxyType)
        self.assertIsInstance(prepared.underlying_bindings, MappingProxyType)
        binding = prepared.underlying_bindings[(_DYNAMIC_HYPOTHESIS_ID, "ACME")]
        self.assertIs(binding[0], key)
        self.assertIs(binding[1], reference)

    def test_existing_bindings_and_date_range_are_fill_only_by_identity(self):
        date_range = MethodologizedDateRange(
            datetime.date(2026, 9, 1),
            datetime.date(2026, 9, 2),
            "independent Host fixture evidence",
        )
        key = UnderlyingKey("ACME", "XNAS", UnderlyingSecurityType.EQUITY, "USD")
        reference = object()
        context = replace(
            self.context,
            event_description_binding="claim-1",
            event_date_range=date_range,
            underlying_bindings={("hyp-1", "ACME"): (key, reference)},
        )
        _, producer, _, _, verdict = _wire_bundle(self.run_input, context)
        old_pair, old_value = next(iter(context.underlying_bindings.items()))

        result, _ = self._invoke(
            lambda snapshot, receipt, original: replace(original),
            context=context,
            producer=producer,
            verdict=verdict,
        )
        built_context = result.build_result.context
        self.assertIs(built_context.event_date_range, date_range)
        retained_pair, retained_value = next(iter(built_context.underlying_bindings.items()))
        self.assertEqual(retained_pair, old_pair)
        self.assertIs(retained_value[0], old_value[0])
        self.assertIs(retained_value[1], old_value[1])
        self.assertEqual(built_context.event_description_binding, "claim-1")

    def test_existing_description_cannot_be_replaced(self):
        context = replace(self.context, event_description_binding="claim-1")
        _, producer, _, _, verdict = _wire_bundle(self.run_input, context)
        with self.assertRaises(HostGrounderRuntimeError) as raised:
            self._invoke(
                lambda snapshot, receipt, original: replace(
                    original, event_description_binding="replacement-claim"
                ),
                context=context,
                producer=producer,
                verdict=verdict,
            )
        self.assertEqual(raised.exception.code, "HOST_CONTEXT_PREPARATION_REJECTED")


if __name__ == "__main__":
    unittest.main()
