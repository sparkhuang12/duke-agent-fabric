package duke.harness_test

import data.duke.harness
import rego.v1

test_owner_can_invoke if {
	harness.decision.allow with input as {
		"action": "agent.invoke",
		"subject": {"tenant_id": "t1", "user_id": "u1", "roles": ["user"], "clearance": "internal"},
		"address": {"tenant_id": "t1", "user_id": "u1"},
		"agent": {"allowed_tools": ["search"], "allowed_roles": ["user"], "require_approval": true},
		"resource": {},
	}
}

test_unlisted_tool_is_denied if {
	not harness.decision.allow with input as {
		"action": "tool.call",
		"subject": {"tenant_id": "t1", "user_id": "u1", "roles": ["user"], "clearance": "internal"},
		"address": {"tenant_id": "t1", "user_id": "u1"},
		"agent": {"allowed_tools": ["search"], "allowed_roles": ["user"], "require_approval": true},
		"resource": {"tool_name": "shell"},
	}
}

test_confidential_run_requires_manual_approval if {
	decision := harness.decision with input as {
		"action": "agent.invoke",
		"subject": {"tenant_id": "t1", "user_id": "u1", "roles": ["user"], "clearance": "confidential"},
		"address": {"tenant_id": "t1", "user_id": "u1"},
		"agent": {"allowed_tools": ["search"], "allowed_roles": ["user"], "require_approval": false},
		"resource": {"security_level": "confidential", "memory_scope": "short_term"},
	}
	decision.allow
	decision.obligations.manual_approval
}

test_confidential_approval_requires_security_approver if {
	not harness.decision.allow with input as {
		"action": "run.approve",
		"subject": {"tenant_id": "t1", "user_id": "reviewer", "roles": ["approver"], "clearance": "secret"},
		"address": {"tenant_id": "t1", "user_id": "u1"},
		"agent": {"allowed_tools": [], "allowed_roles": ["user"], "require_approval": false},
		"resource": {"security_level": "confidential"},
	}
}

test_different_security_approver_can_approve_confidential_run if {
	harness.decision.allow with input as {
		"action": "run.approve",
		"subject": {"tenant_id": "t1", "user_id": "reviewer", "roles": ["security_approver"], "clearance": "secret"},
		"address": {"tenant_id": "t1", "user_id": "u1"},
		"agent": {"allowed_tools": [], "allowed_roles": ["user"], "require_approval": false},
		"resource": {"security_level": "confidential"},
	}
}

test_owner_cannot_self_approve_even_with_reviewer_role if {
	not harness.decision.allow with input as {
		"action": "run.approve",
		"subject": {"tenant_id": "t1", "user_id": "u1", "roles": ["user", "approver"], "clearance": "internal"},
		"address": {"tenant_id": "t1", "user_id": "u1"},
		"agent": {"allowed_tools": [], "allowed_roles": ["user"], "require_approval": true},
		"resource": {"security_level": "internal"},
	}
}
