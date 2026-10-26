from __future__ import annotations

import json
import logging
import os
from io import StringIO
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from dev_workflow_standards_tools.infrastructure import openai_client
from dev_workflow_standards_tools.services import ai_workflow
from dev_workflow_standards_tools.services.ai_workflow import (
    ContentGenerationRequest,
    EvidenceItem,
    GeneratedContent,
    SessionDecisionRequest,
    WorkflowDecisionRequest,
    audit_issue_pr_policy,
    check_branch_names,
    check_commit_message,
    decide_codex_session_action,
    decide_skill_workflow,
    generate_skill_content,
)
from dev_workflow_standards_tools.services.codex_session_facts import CodexSessionSource


API_KEY_A = "sk-test-key-value-aaaaaaaaaaaaaaaa"
API_KEY_B = "sk-test-key-value-bbbbbbbbbbbbbbbb"
BASE_URL_A = "https://api-a.example.invalid/v1"
BASE_URL_B = "https://api-b.example.invalid/v1"
THREAD = "00000000-0000-4000-8000-000000000011"


def choice_answer(name: str, choice: str, values: tuple[str, ...]) -> SimpleNamespace:
    return SimpleNamespace(
        type="choice",
        name=name,
        choice=choice,
        confidence=0.71,
        probabilities=[SimpleNamespace(value=value, probability=1 / len(values)) for value in values],
    )


def decision_response(*answers: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(answers=list(answers), refusal=None)


def configured_env(**overrides: str) -> dict[str, str]:
    return {"OPENAI_API_KEY": API_KEY_A, "OPENAI_BASE_URL": BASE_URL_A, **overrides}


class OpenAIClientTests(unittest.TestCase):
    def test_missing_or_blank_environment_prevents_client_creation(self) -> None:
        cases = [
            {"OPENAI_API_KEY": "", "OPENAI_BASE_URL": BASE_URL_A},
            {"OPENAI_API_KEY": API_KEY_A, "OPENAI_BASE_URL": "   "},
            {},
        ]
        for environment in cases:
            with self.subTest(environment_keys=list(environment)), patch.dict(os.environ, environment, clear=True), patch.object(
                openai_client, "OpenAI"
            ) as factory:
                with self.assertRaises(openai_client.OpenAIWorkflowError):
                    openai_client.create_decision([], [])
                factory.assert_not_called()

    def test_bad_base_url_is_rejected_without_echoing_it(self) -> None:
        for url in (
            "ftp://api.example.invalid/v1",
            "https://user:password@api.example.invalid/v1",
            "https://api.example.invalid/v1?secret=token",
            "https://api.example.invalid/v1#fragment",
        ):
            with self.subTest(url_kind=url.split(":", 1)[0]), patch.dict(
                os.environ, configured_env(OPENAI_BASE_URL=url), clear=True
            ), patch.object(openai_client, "OpenAI") as factory:
                with self.assertRaises(openai_client.OpenAIWorkflowError) as raised:
                    openai_client.create_decision([], [])
                self.assertEqual(raised.exception.error_code, "invalid_base_url")
                self.assertNotIn(url, str(raised.exception))
                factory.assert_not_called()

    def test_each_request_reads_environment_and_passes_explicit_config(self) -> None:
        answer = decision_response(choice_answer("q", "compliant", ("compliant",)))
        first = Mock()
        first.decisions.create.return_value = answer
        second = Mock()
        second.decisions.create.return_value = answer
        with patch.dict(os.environ, configured_env(), clear=True), patch.object(
            openai_client, "OpenAI", side_effect=[first, second]
        ) as factory:
            openai_client.create_decision([], [])
            os.environ["OPENAI_API_KEY"] = API_KEY_B
            os.environ["OPENAI_BASE_URL"] = BASE_URL_B
            openai_client.create_decision([], [])
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(factory.call_args_list[0].kwargs["api_key"], API_KEY_A)
        self.assertEqual(factory.call_args_list[0].kwargs["base_url"], BASE_URL_A)
        self.assertEqual(factory.call_args_list[1].kwargs["api_key"], API_KEY_B)
        self.assertEqual(factory.call_args_list[1].kwargs["base_url"], BASE_URL_B)
        for call in factory.call_args_list:
            self.assertEqual(call.kwargs["timeout"], openai_client.OPENAI_TIMEOUT_SECONDS)
            self.assertEqual(call.kwargs["max_retries"], 0)
            self.assertEqual(set(call.kwargs), {"api_key", "base_url", "timeout", "max_retries"})
        first.close.assert_called_once()
        second.close.assert_called_once()

    def test_secret_or_endpoint_in_payload_is_blocked_before_client_creation(self) -> None:
        for sensitive_value in (API_KEY_A, BASE_URL_A):
            with self.subTest(kind="secret" if sensitive_value == API_KEY_A else "endpoint"), patch.dict(
                os.environ, configured_env(), clear=True
            ), patch.object(openai_client, "OpenAI") as factory:
                with self.assertRaises(openai_client.OpenAIWorkflowError) as raised:
                    openai_client.create_decision([{"role": "user", "content": sensitive_value}], [])
                self.assertEqual(raised.exception.error_code, "sensitive_value_in_request")
                self.assertNotIn(sensitive_value, str(raised.exception))
                factory.assert_not_called()

    def test_api_errors_and_sensitive_responses_are_sanitized(self) -> None:
        fake = Mock()
        fake.decisions.create.side_effect = RuntimeError(f"{API_KEY_A} {BASE_URL_A}")
        with patch.dict(os.environ, configured_env(), clear=True), patch.object(
            openai_client, "OpenAI", return_value=fake
        ):
            with self.assertRaises(openai_client.OpenAIWorkflowError) as raised:
                openai_client.create_decision([], [])
        self.assertEqual(raised.exception.error_code, "api_request_failed")
        self.assertNotIn(API_KEY_A, str(raised.exception))
        self.assertNotIn(BASE_URL_A, str(raised.exception))

        sensitive_response = SimpleNamespace(secret=API_KEY_A)
        fake = Mock()
        fake.decisions.create.return_value = sensitive_response
        with patch.dict(os.environ, configured_env(), clear=True), patch.object(
            openai_client, "OpenAI", return_value=fake
        ):
            with self.assertRaises(openai_client.OpenAIWorkflowError) as raised:
                openai_client.create_decision([], [])
        self.assertEqual(raised.exception.error_code, "sensitive_value_in_response")

    def test_log_records_redact_current_key_and_endpoint_from_child_loggers_and_exceptions(self) -> None:
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger = logging.getLogger("openai.httpx.redaction_test")
        root_logger = logging.getLogger()
        previous_root_handlers = root_logger.handlers[:]
        previous_level = logger.level
        previous_propagate = logger.propagate
        logger.setLevel(logging.DEBUG)
        logger.propagate = True
        for existing_handler in previous_root_handlers:
            root_logger.removeHandler(existing_handler)
        root_logger.addHandler(handler)
        try:
            with patch.dict(os.environ, configured_env(), clear=True):
                logger.info("request configuration %s", API_KEY_A)
                logger.debug("selected endpoint %s", BASE_URL_A)
                try:
                    raise RuntimeError(f"transport failed for {API_KEY_A} at {BASE_URL_A}")
                except RuntimeError:
                    logger.exception("request failed")
            output = stream.getvalue()
            self.assertIn("INFO", output)
            self.assertIn("DEBUG", output)
            self.assertIn("RuntimeError", output)
            self.assertNotIn(API_KEY_A, output)
            self.assertNotIn(BASE_URL_A, output)
            self.assertEqual(output.count("[REDACTED]"), 4)
        finally:
            root_logger.removeHandler(handler)
            for existing_handler in previous_root_handlers:
                root_logger.addHandler(existing_handler)
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
            handler.close()

    def test_decisions_uses_fixed_model_and_no_reasoning_or_store_options(self) -> None:
        fake = Mock()
        fake.decisions.create.return_value = decision_response(
            choice_answer("q", "compliant", ("compliant",))
        )
        question = [{"type": "choice", "name": "q", "instructions": "fixed", "choices": [{"value": "compliant"}]}]
        with patch.dict(os.environ, configured_env(), clear=True), patch.object(
            openai_client, "OpenAI", return_value=fake
        ):
            openai_client.create_decision([{"role": "user", "content": "{}"}], question)
        kwargs = fake.decisions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-6-luna")
        self.assertEqual(kwargs["questions"], question)
        self.assertEqual(set(kwargs), {"model", "input", "questions"})

    def test_responses_parse_uses_effort_store_disabled_and_no_auto_truncation(self) -> None:
        fake = Mock()
        fake.responses.parse.return_value = SimpleNamespace(status="completed")
        schema = GeneratedContent
        with patch.dict(os.environ, configured_env(), clear=True), patch.object(
            openai_client, "OpenAI", return_value=fake
        ):
            openai_client.parse_response(
                instructions="fixed",
                input="{}",
                text_format=schema,
                reasoning_effort="medium",
                max_output_tokens=400,
            )
        kwargs = fake.responses.parse.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-6-luna")
        self.assertEqual(kwargs["reasoning"], {"effort": "medium"})
        self.assertFalse(kwargs["store"])
        self.assertEqual(kwargs["truncation"], "disabled")
        self.assertEqual(kwargs["text_format"], schema)
        self.assertNotIn("tools", kwargs)
        self.assertEqual(set(kwargs), {
            "model", "instructions", "input", "text_format", "reasoning", "store",
            "max_output_tokens", "truncation",
        })


class DecisionAndValidationTests(unittest.TestCase):
    def test_decision_prompts_include_exact_local_rules_and_listed_choice_constraints(self) -> None:
        responses = [
            decision_response(choice_answer("branch_policy", "compliant", ai_workflow.DECISION_CHOICES)),
            decision_response(choice_answer("commit_policy", "compliant", ai_workflow.DECISION_CHOICES)),
        ]
        with patch.object(ai_workflow.openai_client, "create_decision", side_effect=responses) as create:
            branch_result = check_branch_names(["feat/synthetic"])
            commit_result = check_commit_message("feat: 增加合成工具")
        self.assertTrue(branch_result["passed"])
        self.assertTrue(commit_result["passed"])
        branch_input, branch_questions = create.call_args_list[0].args
        commit_input, commit_questions = create.call_args_list[1].args
        branch_facts = json.loads(branch_input[0]["content"])
        commit_facts = json.loads(commit_input[0]["content"])
        branch_prompt = branch_questions[0]["instructions"]
        commit_prompt = commit_questions[0]["instructions"]
        self.assertEqual(branch_facts, {"branch_checks": [{"branch_name": "feat/synthetic", "passed": True}]})
        self.assertEqual(commit_facts, {
            "inspected_commit": {
                "subject": "feat: 增加合成工具",
                "subject_format_valid": True,
                "chinese_description_present": True,
                "prohibited_attribution_present": False,
            }
        })
        for expected in (
            repr(sorted(ai_workflow.ROOT_BRANCH_NAMES)),
            repr(ai_workflow.WORK_BRANCH_PATTERN.pattern),
            repr(ai_workflow.FORBIDDEN_AGENT_NAMES),
        ):
            self.assertIn(expected, branch_prompt)
            self.assertNotIn(expected, json.dumps(branch_facts, ensure_ascii=False))
        for expected in (
            repr(ai_workflow.SUBJECT_PATTERN.pattern),
            repr(ai_workflow.CHINESE_PATTERN.pattern),
            repr(ai_workflow.ATTRIBUTION_PATTERN.pattern),
            "The Chinese word '工具' alone is ordinary description, not attribution.",
            "Do not add style preferences",
        ):
            self.assertIn(expected, commit_prompt)
            self.assertNotIn(expected, json.dumps(commit_facts, ensure_ascii=False))
        self.assertNotIn("commit_message", commit_facts)
        self.assertNotIn("rules", commit_facts)
        commit_choices = {item["value"]: item["description"] for item in commit_questions[0]["choices"]}
        self.assertIn("subject_format_valid=false", commit_choices["requires_fix"])
        self.assertIn("chinese_description_present=false", commit_choices["requires_fix"])
        self.assertIn("prohibited_attribution_present=true", commit_choices["requires_fix"])
        for prompt in (branch_prompt, commit_prompt):
            self.assertIn("Never invent a choice value", prompt)
            self.assertIn("only if this question lists one", prompt)
            self.assertNotIn("select insufficient_evidence", prompt)

    def test_commit_attribution_uses_local_comment_filter_but_checks_body(self) -> None:
        comment_only = "feat: 增加功能\n# Generated with Codex\n"
        with patch.object(
            ai_workflow.openai_client,
            "create_decision",
            return_value=decision_response(choice_answer("commit_policy", "compliant", ai_workflow.DECISION_CHOICES)),
        ) as create:
            accepted = check_commit_message(comment_only)
        self.assertTrue(accepted["passed"])
        submitted_facts = json.loads(create.call_args.args[0][0]["content"])
        self.assertFalse(submitted_facts["inspected_commit"]["prohibited_attribution_present"])

        body_attribution = "feat: 增加功能\n实现了用户请求的能力。\nGenerated with Codex"
        with patch.object(ai_workflow.openai_client, "create_decision") as create:
            rejected = check_commit_message(body_attribution)
        create.assert_not_called()
        self.assertFalse(rejected["passed"])
        self.assertIn("禁止包含工具署名", " ".join(rejected["errors"]))

    def test_issue_pr_single_object_requests_are_valid_and_false_flags_mean_not_requested(self) -> None:
        for requested, kwargs in (
            ("issue", {"issue_number": 4}),
            ("pr", {"pr_number": 5}),
        ):
            with self.subTest(requested=requested), patch.object(
                ai_workflow.validation,
                "audit_issue_pr_policy",
                return_value={"passed": True, "errors": []},
            ), patch.object(
                ai_workflow.openai_client,
                "create_decision",
                return_value=decision_response(
                    choice_answer("issue_pr_policy", "compliant", ai_workflow.DECISION_CHOICES)
                ),
            ) as create:
                result = audit_issue_pr_policy("/synthetic/repo", **kwargs)
            self.assertTrue(result["passed"])
            facts = json.loads(create.call_args.args[0][0]["content"])
            self.assertEqual(facts["issue_requested"], requested == "issue")
            self.assertEqual(facts["pull_request_requested"], requested == "pr")
            self.assertFalse(facts["expected_base_checked"])
            self.assertFalse(facts["expected_head_checked"])
            prompt = create.call_args.args[1][0]["instructions"]
            self.assertIn("false mean that comparison was not requested", prompt)
            self.assertIn("Issue-only and PR-only audits are valid", prompt)
            self.assertIn("Do not infer CI, labels, repository identity, mergeability", prompt)
            self.assertIn("Apply only the requested-scope checks defined in this question's instructions", prompt)
            self.assertIn("Do not add checks for unrequested objects, fields, or external conditions", prompt)
            self.assertNotIn("required issue-closing reference", prompt)

    def test_invalid_local_check_skips_decisions_and_never_passes(self) -> None:
        local = {"passed": False, "checks": [{"branch_name": "bad", "passed": False, "errors": ["hard error"]}]}
        with patch.object(ai_workflow.validation, "check_branch_names", return_value=local), patch.object(
            ai_workflow.openai_client, "create_decision"
        ) as create:
            result = check_branch_names(["bad"])
        create.assert_not_called()
        self.assertFalse(result["passed"])
        self.assertFalse(result["local_passed"])
        self.assertEqual(result["checks"], local["checks"])
        self.assertEqual(result["ai_status"], "skipped_local_failure")

    def test_local_failure_cannot_be_flipped_by_compliant_decision(self) -> None:
        local = {"passed": False, "subject": "bad", "errors": ["local rule"]}
        with patch.object(ai_workflow.validation, "check_commit_message", return_value=local), patch.object(
            ai_workflow.openai_client,
            "create_decision",
            return_value=decision_response(choice_answer("commit_policy", "compliant", ai_workflow.DECISION_CHOICES)),
        ) as create:
            result = check_commit_message("bad")
        create.assert_not_called()
        self.assertFalse(result["passed"])
        self.assertEqual(result["errors"], ["local rule"])

    def test_local_pass_requires_compliant_decision(self) -> None:
        local = {"passed": True, "subject": "docs: 文档", "errors": []}
        fake_response = decision_response(
            choice_answer("commit_policy", "requires_fix", ai_workflow.DECISION_CHOICES)
        )
        with patch.object(ai_workflow.validation, "check_commit_message", return_value=local), patch.object(
            ai_workflow.openai_client, "create_decision", return_value=fake_response
        ):
            result = check_commit_message("docs: 文档")
        self.assertFalse(result["passed"])
        self.assertTrue(result["local_passed"])
        self.assertEqual(result["decision"], "requires_fix")
        self.assertTrue(result["requires_agent_review"])

    def test_sensitive_commit_input_is_not_echoed_when_api_request_is_blocked(self) -> None:
        for sensitive_value in (API_KEY_A, BASE_URL_A):
            message = f"docs: 文档 {sensitive_value}"
            with self.subTest(kind="key" if sensitive_value == API_KEY_A else "base_url"), patch.dict(
                os.environ, configured_env(), clear=True
            ), patch.object(openai_client, "OpenAI") as factory:
                result = check_commit_message(message)
            factory.assert_not_called()
            self.assertFalse(result["passed"])
            self.assertTrue(result["local_passed"])
            self.assertEqual(result["error_code"], "sensitive_value_in_request")
            self.assertNotIn(sensitive_value, json.dumps(result))
            self.assertNotIn("subject", result)

    def test_issue_pr_api_input_omits_repo_path_repo_and_raw_body(self) -> None:
        local = {"passed": True, "repo": "private/example", "errors": []}
        result = decision_response(
            choice_answer("issue_pr_policy", "compliant", ai_workflow.DECISION_CHOICES)
        )
        with patch.object(ai_workflow.validation, "audit_issue_pr_policy", return_value=local), patch.object(
            ai_workflow.openai_client, "create_decision", return_value=result
        ) as create:
            wrapped = audit_issue_pr_policy("/secret/repo", repo="private/example", issue_number=4, pr_number=5)
        self.assertTrue(wrapped["passed"])
        payload = json.dumps(create.call_args.args[0], ensure_ascii=False)
        self.assertNotIn("/secret/repo", payload)
        self.assertNotIn("private/example", payload)
        self.assertNotIn("body", payload)

    def test_decision_answer_shape_choice_and_unique_name_are_strict(self) -> None:
        question = {
            "name": "q",
            "choices": [{"value": value} for value in ai_workflow.DECISION_CHOICES],
        }
        valid = choice_answer("q", "compliant", ai_workflow.DECISION_CHOICES)
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=decision_response(valid)):
            self.assertEqual(ai_workflow._decisions([question], {}), {"q": "compliant"})
        refusal = SimpleNamespace(type="refusal", name="q")
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=decision_response(refusal)):
            self.assertEqual(ai_workflow._decisions([question], {}), {"error_code": "invalid_decision_response"})
        bad = choice_answer("q", "not-an-option", ai_workflow.DECISION_CHOICES)
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=decision_response(bad)):
            self.assertEqual(ai_workflow._decisions([question], {}), {"error_code": "invalid_decision_response"})
        duplicate = decision_response(valid, valid)
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=duplicate):
            self.assertEqual(ai_workflow._decisions([question], {}), {"error_code": "invalid_decision_response"})

    def test_workflow_priority_and_no_implicit_worktree(self) -> None:
        request = WorkflowDecisionRequest(
            user_request="实现普通开发任务",
            explicit_worktree=False,
            github_delivery=True,
            verification_only=True,
            special_operations=True,
            blocked=False,
        )
        result = decision_response(
            choice_answer("workflow", "github-delivery", ai_workflow.WORKFLOW_CHOICES)
        )
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=result) as create:
            advised = decide_skill_workflow(request)
        self.assertEqual(advised["workflow"], "github-delivery")
        self.assertEqual(advised["model"], "gpt-6-luna")
        self.assertTrue(advised["requires_agent_review"])
        self.assertFalse(advised["side_effects"])
        self.assertEqual(advised["rules_hash"], ai_workflow._fingerprint(create.call_args.args[1]))
        api_input, questions = create.call_args.args
        self.assertEqual(len(api_input), 1)
        self.assertEqual(api_input[0]["role"], "user")
        self.assertEqual(json.loads(api_input[0]["content"]), request.model_dump(mode="json"))
        workflow_instructions = questions[0]["instructions"]
        for phrase in (
            "blocked=true selects recovery-and-exceptions",
            "explicit_worktree=true selects worktree-development",
            "github_delivery=true selects github-delivery",
            "special_operations=true selects special-operations",
            "verification_only=true selects verification-and-cleanup",
            "If all five flags are false, select standard-development",
            "A missing repository path, unavailable tool, or lack of execution access is not a reason to clarify",
        ):
            self.assertIn(phrase, workflow_instructions)

        worktree = decision_response(
            choice_answer("workflow", "worktree-development", ai_workflow.WORKFLOW_CHOICES)
        )
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=worktree):
            rejected = decide_skill_workflow(
                WorkflowDecisionRequest(
                    user_request="普通任务",
                    explicit_worktree=False,
                    github_delivery=False,
                    verification_only=False,
                    special_operations=False,
                    blocked=False,
                )
            )
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["error_code"], "decision_inconsistent_with_workflow_rules")

    def test_strict_workflow_input_rejects_string_boolean_and_unknown_model(self) -> None:
        data = {
            "user_request": "任务",
            "explicit_worktree": "false",
            "github_delivery": False,
            "verification_only": False,
            "special_operations": False,
            "blocked": False,
        }
        with self.assertRaises(ValidationError):
            WorkflowDecisionRequest.model_validate(data)
        data["explicit_worktree"] = False
        data["model"] = "another-model"
        with self.assertRaises(ValidationError):
            WorkflowDecisionRequest.model_validate(data)

    def test_session_actions_enforce_source_access_and_persistence_bounds(self) -> None:
        request = SessionDecisionRequest(
            user_request="检查历史背景",
            has_relevant_sources=True,
            history_accessible=True,
            history_fully_read=True,
            relevant_facts_found=True,
            persistence_allowed=False,
            existing_summary=False,
            new_fact_origin="original_session",
        )
        response = decision_response(
            choice_answer("lookup_action", "read_history", ai_workflow.SESSION_LOOKUP_CHOICES),
            choice_answer("persistence_action", "skip_persistence", ai_workflow.SESSION_PERSISTENCE_CHOICES),
        )
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=response) as create:
            result = decide_codex_session_action(request)
        self.assertEqual(result["lookup_action"], "read_history")
        self.assertEqual(result["persistence_action"], "skip_persistence")
        self.assertFalse(result["metadata_verified"])
        self.assertTrue(result["requires_agent_review"])
        self.assertEqual(result["rules_hash"], ai_workflow._fingerprint(create.call_args.args[1]))
        self.assertEqual(create.call_args.args[0][0]["role"], "user")
        lookup_prompt, persistence_prompt = [q["instructions"] for q in create.call_args.args[1]]
        self.assertIn("if has_relevant_sources=false, choose query_project", lookup_prompt)
        self.assertIn("if history_accessible=false, choose blocked", lookup_prompt)
        self.assertIn("rely on and trace the already-read evidence without repeating I/O unnecessarily", lookup_prompt)
        self.assertNotIn("existing_summary=true", lookup_prompt)
        self.assertIn("if persistence_allowed=false or new_fact_origin is current_session or none", persistence_prompt)
        self.assertIn("if has_relevant_sources=false, choose skip_persistence", persistence_prompt)
        self.assertIn("choose update_summary when existing_summary=true or create_summary when false", persistence_prompt)
        self.assertNotIn("choose query_project", persistence_prompt)

    def test_session_model_cannot_create_on_current_facts_or_skip_source_block(self) -> None:
        current = SessionDecisionRequest(
            user_request="归纳当前发现",
            has_relevant_sources=True,
            history_accessible=True,
            history_fully_read=True,
            relevant_facts_found=True,
            persistence_allowed=True,
            existing_summary=False,
            new_fact_origin="current_session",
        )
        bad_response = decision_response(
            choice_answer("lookup_action", "read_history", ai_workflow.SESSION_LOOKUP_CHOICES),
            choice_answer("persistence_action", "create_summary", ai_workflow.SESSION_PERSISTENCE_CHOICES),
        )
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=bad_response):
            rejected = decide_codex_session_action(current)
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["error_code"], "decision_inconsistent_with_session_rules")

        unavailable = SessionDecisionRequest(
            user_request="查历史",
            has_relevant_sources=True,
            history_accessible=False,
            history_fully_read=False,
            relevant_facts_found=None,
            persistence_allowed=True,
            existing_summary=True,
            new_fact_origin="original_session",
        )
        good_blocked = decision_response(
            choice_answer("lookup_action", "blocked", ai_workflow.SESSION_LOOKUP_CHOICES),
            choice_answer("persistence_action", "await_source_evidence", ai_workflow.SESSION_PERSISTENCE_CHOICES),
        )
        with patch.object(ai_workflow.openai_client, "create_decision", return_value=good_blocked):
            allowed = decide_codex_session_action(unavailable)
        self.assertEqual(allowed["lookup_action"], "blocked")
        self.assertEqual(allowed["persistence_action"], "await_source_evidence")


class ContentGenerationTests(unittest.TestCase):
    def _generated(self, refs: list[str] | None = None) -> GeneratedContent:
        return GeneratedContent(
            title="候选标题",
            content="候选正文。",
            used_evidence_refs=refs or [],
            missing_facts=["缺少结果证据"],
            review_notes=["需Agent核对"],
        )

    def _completed(self, parsed: GeneratedContent | None, *, status: str = "completed", refusal: bool = False):
        content = [SimpleNamespace(type="refusal", refusal="no")] if refusal else []
        return SimpleNamespace(
            status=status,
            output_parsed=parsed,
            output=[SimpleNamespace(content=content)] if content else [],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20, total_tokens=30, secret="ignored"),
        )

    def test_each_kind_sends_substantive_audience_structure_and_evidence_rules(self) -> None:
        source = CodexSessionSource(
            source_link=f"codex://threads/{THREAD}", created_at="2026-01-01T00:00:00Z", title="历史会话"
        )
        expectations = {
            "issue": ("repository maintainers", "defect report or a feature/change request", "reproduction steps only when those steps are present"),
            "pr": ("reviewers deciding whether a proposed change is ready", "verification actually evidenced", "issue number or link only when that identifier is in evidence", "without explicit evidence"),
            "commit_message": ("readers of version history", "complete commit subject", "optional body"),
            "plan": ("Agent carrying out the work", "proposed action", "proposed verification method"),
            "handoff": ("next Agent or collaborator", "unfinished work", "Distinguish next steps recorded in the source from recommendations"),
            "session_summary": ("future Agent resuming this exact original session", "single source.thread_id", "If the requested layout presents ended_at and it is absent/null"),
        }
        for kind, phrases in expectations.items():
            with self.subTest(kind=kind):
                evidence = [EvidenceItem(
                    reference_id="F1",
                    content="原会话事实" if kind == "session_summary" else "本次任务事实",
                    origin="provided_session" if kind == "session_summary" else "user_provided",
                    source_thread_id=THREAD if kind == "session_summary" else None,
                )]
                request = ContentGenerationRequest(
                    kind=kind,
                    user_request="Draft the requested deliverable",
                    evidence=evidence,
                    source=source if kind == "session_summary" else None,
                )
                candidate = GeneratedContent(
                    title="docs: 增加测试" if kind == "commit_message" else "候选标题",
                    content="" if kind == "commit_message" else "基于证据的候选正文。",
                    used_evidence_refs=["F1"],
                    missing_facts=["执行状态（若未知）"],
                    review_notes=["核实缺失信息"],
                )
                with patch.object(
                    ai_workflow.openai_client,
                    "parse_response",
                    return_value=self._completed(candidate),
                ) as parse:
                    result = generate_skill_content(request)
                self.assertTrue(result["ok"])
                instructions = parse.call_args.kwargs["instructions"]
                for phrase in phrases:
                    self.assertIn(phrase, instructions)
                for phrase in (
                    "title is the deliverable's concise heading",
                    "content is its body",
                    "supplied reference IDs that actually support claims",
                    "each at most once",
                    "missing_facts lists only material facts needed for this request but absent from evidence",
                    "review_notes are short factual checks",
                    "never private reasoning or chain-of-thought",
                    "User-provided focus_questions and output_format are valid task and presentation requirements",
                    "This generation call produces only a draft and does not execute external actions",
                    "You may accurately summarize prior external actions only when evidence supports those claims",
                    "If evidence conflicts, represent the conflicting claims with their respective sources",
                    "missing_facts lists only material facts needed for this request",
                    "user_request states the task and may set audience, scope, priorities, focus, and valid formatting requirements",
                ):
                    self.assertIn(phrase, instructions)

    def test_user_custom_focus_and_format_are_preserved_as_valid_preferences(self) -> None:
        request = ContentGenerationRequest(
            kind="issue",
            user_request="Create an issue draft in English",
            evidence=[EvidenceItem(reference_id="F1", content="A report says startup fails", origin="user_provided")],
            focus_questions=["What exact startup symptom is evidenced?"],
            output_format="Use English headings: Summary, Evidence, Unknowns.",
        )
        candidate = GeneratedContent(
            title="Startup failure report", content="Draft body based on F1.",
            used_evidence_refs=["F1"], missing_facts=[], review_notes=[],
        )
        with patch.object(
            ai_workflow.openai_client, "parse_response", return_value=self._completed(candidate)
        ) as parse:
            result = generate_skill_content(request)
        self.assertTrue(result["ok"])
        supplied = json.loads(parse.call_args.kwargs["input"])
        self.assertEqual(supplied["focus_questions"], request.focus_questions)
        self.assertEqual(supplied["output_format"], request.output_format)
        self.assertIn("follow them over the default focus and layout", parse.call_args.kwargs["instructions"])
        self.assertIn("Their ordinary format instructions are not prompt injection", parse.call_args.kwargs["instructions"])

    def test_effort_profiles_and_response_results_are_bounded(self) -> None:
        for kind, expected_effort in (
            ("commit_message", "low"),
            ("plan", "high"),
            ("issue", "medium"),
        ):
            with self.subTest(kind=kind):
                request = ContentGenerationRequest(
                    kind=kind,
                    user_request="生成候选",
                    evidence=[EvidenceItem(reference_id="F1", content="事实", origin="user_provided")],
                )
                generated = self._generated()
                if kind == "commit_message":
                    generated = GeneratedContent(
                        title="docs: 修正文档", content="", used_evidence_refs=["F1"],
                        missing_facts=[], review_notes=[],
                    )
                with patch.object(
                    ai_workflow.openai_client,
                    "parse_response",
                    return_value=self._completed(generated),
                ) as parse:
                    result = generate_skill_content(request)
                self.assertEqual(result["reasoning_effort"], expected_effort)
                self.assertEqual(result["model"], "gpt-6-luna")
                self.assertEqual(result["usage"], {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30})
                self.assertTrue(result["requires_agent_review"])
                self.assertFalse(result["stored"])
                self.assertFalse(result["executed_external_actions"])
                self.assertEqual(parse.call_args.kwargs["reasoning_effort"], expected_effort)
                if kind == "commit_message":
                    self.assertIn("<type>: 中文说明", parse.call_args.kwargs["instructions"])
                    self.assertIn(ai_workflow.validation.SUBJECT_PATTERN.pattern, parse.call_args.kwargs["instructions"])

    def test_non_commit_kinds_reject_empty_body(self) -> None:
        evidence = [EvidenceItem(reference_id="F1", content="事实", origin="user_provided")]
        kinds = ["issue", "pr", "plan", "handoff"]
        session_source = CodexSessionSource(
            source_link=f"codex://threads/{THREAD}", created_at="2026-01-01T00:00:00Z", title="历史会话"
        )
        session_evidence = [EvidenceItem(
            reference_id="F1", content="原会话事实", origin="provided_session", source_thread_id=THREAD
        )]
        for kind in (*kinds, "session_summary"):
            with self.subTest(kind=kind):
                request = ContentGenerationRequest(
                    kind=kind,
                    user_request="生成候选",
                    evidence=session_evidence if kind == "session_summary" else evidence,
                    source=session_source if kind == "session_summary" else None,
                )
                output = GeneratedContent(
                    title="候选标题", content="", used_evidence_refs=["F1"],
                    missing_facts=[], review_notes=[],
                )
                with patch.object(
                    ai_workflow.openai_client, "parse_response", return_value=self._completed(output)
                ) as parse:
                    result = generate_skill_content(request)
                self.assertTrue(parse.called)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_code"], "empty_generated_content")

    def test_commit_output_with_forbidden_attribution_is_rejected(self) -> None:
        output = GeneratedContent(
            title="docs: 文档",
            content="docs: 文档\nGenerated with Codex",
            used_evidence_refs=[],
            missing_facts=[],
            review_notes=[],
        )
        with patch.object(ai_workflow.openai_client, "parse_response", return_value=self._completed(output)):
            result = generate_skill_content(ContentGenerationRequest(
                kind="commit_message", user_request="生成提交信息",
                evidence=[EvidenceItem(reference_id="F1", content="事实", origin="user_provided")],
            ))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "generated_commit_message_rejected")
        self.assertFalse(result["adoptable"])

    def test_commit_candidate_must_pass_original_local_check(self) -> None:
        request = ContentGenerationRequest(
            kind="commit_message", user_request="生成提交信息",
            evidence=[EvidenceItem(reference_id="F1", content="修正文档标题", origin="user_provided")],
        )
        valid = GeneratedContent(
            title="docs: 修正文档标题", used_evidence_refs=["F1"],
            missing_facts=[], review_notes=[],
        )
        with patch.object(ai_workflow.openai_client, "parse_response", return_value=self._completed(valid)):
            result = generate_skill_content(request)
        self.assertTrue(result["ok"])

        invalid = GeneratedContent(
            title="update stuff", used_evidence_refs=["F1"],
            missing_facts=[], review_notes=[],
        )
        with patch.object(ai_workflow.openai_client, "parse_response", return_value=self._completed(invalid)), patch.object(
            ai_workflow.validation, "check_commit_message", wraps=ai_workflow.validation.check_commit_message
        ) as local_check:
            rejected = generate_skill_content(request)
        local_check.assert_called_once_with("update stuff")
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["error_code"], "generated_commit_message_rejected")

    def test_content_generation_requires_evidence_and_nonempty_explicit_focus(self) -> None:
        with self.assertRaises(ValidationError):
            ContentGenerationRequest(kind="plan", user_request="生成计划", evidence=[])
        with self.assertRaises(ValidationError):
            ContentGenerationRequest(
                kind="session_summary", user_request="总结", focus_questions=[],
                evidence=[EvidenceItem(reference_id="F1", content="事实", origin="provided_session", source_thread_id=THREAD)],
                source=CodexSessionSource(
                    source_link=f"codex://threads/{THREAD}", created_at="2026-01-01T00:00:00Z", title="历史会话"
                ),
            )

    def test_response_refusal_incomplete_empty_parse_and_invalid_citations_fail_closed(self) -> None:
        request = ContentGenerationRequest(
            kind="plan",
            user_request="生成计划",
            evidence=[EvidenceItem(reference_id="F1", content="事实", origin="user_provided")],
        )
        cases = [
            (self._completed(self._generated(["F1"]), refusal=True), "model_refusal"),
            (self._completed(self._generated(["F1"]), status="incomplete"), "incomplete_response"),
            (self._completed(None), "invalid_structured_output"),
            (self._completed(self._generated(["unknown"])), "invalid_evidence_reference"),
            (self._completed(self._generated(["F1", "F1"])), "invalid_evidence_reference"),
        ]
        for response, expected in cases:
            with self.subTest(error=expected), patch.object(
                ai_workflow.openai_client, "parse_response", return_value=response
            ):
                result = generate_skill_content(request)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], expected)

    def test_session_summary_requires_matching_original_session_evidence(self) -> None:
        source = CodexSessionSource(
            source_link=f"codex://threads/{THREAD}",
            created_at="2026-01-01T00:00:00Z",
            title="历史会话",
        )
        with self.assertRaises(ValidationError):
            ContentGenerationRequest(
                kind="session_summary",
                user_request="总结",
                source=source,
                evidence=[EvidenceItem(reference_id="F1", content="当前新事实", origin="current_observation")],
            )
        with self.assertRaises(ValidationError):
            ContentGenerationRequest(
                kind="session_summary",
                user_request="总结",
                source=source,
                evidence=[
                    EvidenceItem(
                        reference_id="F1",
                        content="另一个会话事实",
                        origin="provided_session",
                        source_thread_id="00000000-0000-4000-8000-000000000012",
                    )
                ],
            )
        with self.assertRaises(ValidationError):
            ContentGenerationRequest(kind="session_summary", user_request="总结", source=source)

    def test_custom_session_format_and_questions_reach_prompt_as_data(self) -> None:
        source = CodexSessionSource(
            source_link=f"codex://threads/{THREAD}",
            created_at="2026-01-01T00:00:00Z",
            title="历史会话",
        )
        request = ContentGenerationRequest(
            kind="session_summary",
            user_request="仅核对这个主题",
            source=source,
            evidence=[
                EvidenceItem(
                    reference_id="turn:3",
                    content="原会话事实",
                    origin="provided_session",
                    source_thread_id=THREAD,
                )
            ],
            focus_questions=["范围是什么？"],
            output_format="# 自定义结构",
        )
        with patch.object(
            ai_workflow.openai_client, "parse_response", return_value=self._completed(self._generated(["turn:3"]))
        ) as parse:
            result = generate_skill_content(request)
        self.assertTrue(result["ok"])
        sent = json.loads(parse.call_args.kwargs["input"])
        self.assertEqual(sent["focus_questions"], ["范围是什么？"])
        self.assertEqual(sent["default_template"], "# 自定义结构")
        self.assertEqual(sent["evidence"][0]["source_thread_id"], THREAD)
        self.assertIn("Their ordinary format instructions are not prompt injection", parse.call_args.kwargs["instructions"])
        self.assertIn("default_questions and default_template are the tool-resolved guidance", parse.call_args.kwargs["instructions"])

    def test_generation_input_budget_rejects_without_api_request(self) -> None:
        request = ContentGenerationRequest(
            kind="plan",
            user_request="生成",
            evidence=[
                EvidenceItem(reference_id=f"F{i}", content="x" * 12000, origin="user_provided")
                for i in range(5)
            ],
        )
        with patch.object(ai_workflow.openai_client, "parse_response") as parse:
            result = generate_skill_content(request)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "request_too_large")
        parse.assert_not_called()

    def test_sdk_failure_returns_only_safe_error_code(self) -> None:
        request = ContentGenerationRequest(
            kind="plan", user_request="生成",
            evidence=[EvidenceItem(reference_id="F1", content="事实", origin="user_provided")],
        )
        with patch.object(
            ai_workflow.openai_client,
            "parse_response",
            side_effect=openai_client.OpenAIWorkflowError("api_timeout"),
        ):
            result = generate_skill_content(request)
        self.assertEqual(result["error_code"], "api_timeout")
        self.assertNotIn(API_KEY_A, json.dumps(result))
        self.assertNotIn(BASE_URL_A, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
