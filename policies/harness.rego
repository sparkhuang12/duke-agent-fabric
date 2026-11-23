package duke.harness

import rego.v1

default decision := {
	"allow": false,
	"reasons": ["request denied by default"],
	"obligations": {},
}

owner_context if {
	input.subject.tenant_id == input.address.tenant_id
	input.subject.user_id == input.address.user_id
}

approval_access if {
	input.action == "run.approve"
	input.subject.tenant_id == input.address.tenant_id
	input.subject.user_id != input.address.user_id
	input.resource.security_level in {"confidential", "secret"}
	"security_approver" in input.subject.roles
}

approval_access if {
	input.action == "run.approve"
	input.subject.tenant_id == input.address.tenant_id
	input.subject.user_id != input.address.user_id
	input.resource.security_level in {"public", "internal"}
	some role in input.subject.roles
	role in {"approver", "security_approver"}
}

subject_allowed if {
	input.action != "run.approve"
	owner_context
}

subject_allowed if approval_access

action_allowed if input.action in {"agent.invoke", "agent.output", "context.read", "run.read", "run.approve"}

agent_role_allowed if input.action == "run.approve"

agent_role_allowed if {
	some role in input.subject.roles
	role in input.agent.allowed_roles
}

security_rank := {"public": 0, "internal": 1, "confidential": 2, "secret": 3}

clearance_allowed if {
	not input.resource.security_level
}

clearance_allowed if {
	security_rank[input.subject.clearance] >= security_rank[input.resource.security_level]
}

default manual_approval := false

manual_approval if input.agent.require_approval
manual_approval if input.resource.security_level in {"confidential", "secret"}
manual_approval if input.resource.memory_scope == "long_term"

decision := {
	"allow": true,
	"reasons": [],
	"obligations": {"manual_approval": manual_approval},
} if {
	subject_allowed
	action_allowed
	agent_role_allowed
	clearance_allowed
}
