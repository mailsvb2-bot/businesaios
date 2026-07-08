use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

use crate::{
    validate_blast_radius, validate_idempotency_transition, validate_outbox_transition,
    validate_tenant_scope, IdempotencyState, OutboxState, SafetyVerdict, TenantScope,
};

#[derive(Debug, Deserialize)]
pub struct UserScenarioPayload {
    pub version: String,
    pub cases: Vec<UserScenarioCase>,
}

#[derive(Debug, Deserialize)]
pub struct UserScenarioCase {
    pub name: String,
    pub scenario: String,
    pub input: UserScenarioInput,
    pub expected: ExpectedScenarioVerdict,
}

#[derive(Debug, Deserialize)]
pub struct UserScenarioInput {
    pub entrypoint: String,
    pub tenant_id: String,
    pub business_id: String,
    pub binding_tenant_id: String,
    pub goal: String,
    pub requested_outbound: u64,
    pub approved_limit: u64,
    pub idempotency_from: String,
    pub idempotency_to: String,
    pub outbox_from: String,
    pub outbox_to: String,
    pub evidence_required: bool,
}

#[derive(Debug, Deserialize)]
pub struct ExpectedScenarioVerdict {
    pub allowed: bool,
    pub reason: String,
}

#[derive(Debug, Serialize)]
pub struct UserScenarioMatrixReport {
    pub version: String,
    pub passed: bool,
    pub total_cases: usize,
    pub cases: Vec<UserScenarioCaseReport>,
}

#[derive(Debug, Serialize)]
pub struct UserScenarioCaseReport {
    pub name: String,
    pub scenario: String,
    pub entrypoint: String,
    pub allowed: bool,
    pub reason: String,
    pub expected_allowed: bool,
    pub expected_reason: String,
    pub passed: bool,
}

pub fn load_user_scenario_payload(path: &Path) -> Result<UserScenarioPayload, String> {
    let text = fs::read_to_string(path)
        .map_err(|err| format!("user_scenario_fixture_read_failed:{err}"))?;
    let payload: UserScenarioPayload = serde_json::from_str(&text)
        .map_err(|err| format!("user_scenario_fixture_parse_failed:{err}"))?;
    if payload.version != "businessaios_user_scenario_matrix.v1" {
        return Err(format!("user_scenario_fixture_version_mismatch:{}", payload.version));
    }
    Ok(payload)
}

pub fn run_user_scenario_matrix_file(path: &Path) -> Result<(), String> {
    let report = run_user_scenario_matrix_report(path)?;
    if !report.passed {
        let first = report
            .cases
            .iter()
            .find(|item| !item.passed)
            .map(|item| {
                format!(
                    "{}: expected allowed={} reason={} got allowed={} reason={}",
                    item.name, item.expected_allowed, item.expected_reason, item.allowed, item.reason
                )
            })
            .unwrap_or_else(|| "unknown user scenario matrix failure".to_string());
        return Err(format!("user_scenario_case_failed:{first}"));
    }
    Ok(())
}

pub fn run_user_scenario_matrix_report(path: &Path) -> Result<UserScenarioMatrixReport, String> {
    let payload = load_user_scenario_payload(path)?;
    let mut cases = Vec::with_capacity(payload.cases.len());
    let mut passed = true;

    for case in payload.cases.iter() {
        let actual = evaluate_user_scenario_case(case)?;
        let allowed = matches!(actual, SafetyVerdict::Allow);
        let reason = verdict_reason(&actual);
        let case_passed = allowed == case.expected.allowed && reason == case.expected.reason;
        passed = passed && case_passed;
        cases.push(UserScenarioCaseReport {
            name: case.name.clone(),
            scenario: case.scenario.clone(),
            entrypoint: case.input.entrypoint.clone(),
            allowed,
            reason,
            expected_allowed: case.expected.allowed,
            expected_reason: case.expected.reason.clone(),
            passed: case_passed,
        });
    }

    Ok(UserScenarioMatrixReport {
        version: payload.version,
        passed,
        total_cases: payload.cases.len(),
        cases,
    })
}

pub fn evaluate_user_scenario_case(case: &UserScenarioCase) -> Result<SafetyVerdict, String> {
    if !matches!(
        case.scenario.as_str(),
        "capability_matrix" | "connector_matrix" | "cli_run" | "cli_scenario" | "sdk_execute"
    ) {
        return Err(format!("unknown_user_scenario:{}", case.scenario));
    }

    if !matches!(case.input.entrypoint.as_str(), "cli" | "sdk" | "headless") {
        return Ok(SafetyVerdict::Deny { reason: "entrypoint_not_supported" });
    }

    if case.input.goal.trim().is_empty() {
        return Ok(SafetyVerdict::Deny { reason: "goal_required" });
    }

    let tenant = validate_tenant_scope(TenantScope {
        tenant_id: case.input.tenant_id.as_str(),
        business_id: case.input.business_id.as_str(),
        binding_tenant_id: case.input.binding_tenant_id.as_str(),
        allow_global_fallback: false,
    });
    if !tenant.is_allow() {
        return Ok(tenant);
    }

    let blast = validate_blast_radius(case.input.requested_outbound, case.input.approved_limit);
    if !blast.is_allow() {
        return Ok(blast);
    }

    let idempotency = validate_idempotency_transition(
        idempotency_state(case.input.idempotency_from.as_str())?,
        idempotency_state(case.input.idempotency_to.as_str())?,
    );
    if !idempotency.is_allow() {
        return Ok(idempotency);
    }

    let outbox = validate_outbox_transition(
        outbox_state(case.input.outbox_from.as_str())?,
        outbox_state(case.input.outbox_to.as_str())?,
    );
    if !outbox.is_allow() {
        return Ok(outbox);
    }

    if !case.input.evidence_required {
        return Ok(SafetyVerdict::Deny { reason: "evidence_required" });
    }

    Ok(SafetyVerdict::Allow)
}

pub fn verdict_reason(verdict: &SafetyVerdict) -> String {
    match verdict {
        SafetyVerdict::Allow => "allow".to_string(),
        SafetyVerdict::Deny { reason } => reason.to_string(),
    }
}

fn idempotency_state(value: &str) -> Result<IdempotencyState, String> {
    match value {
        "new" => Ok(IdempotencyState::New),
        "reserved" => Ok(IdempotencyState::Reserved),
        "committed" => Ok(IdempotencyState::Committed),
        "failed_retryable" => Ok(IdempotencyState::FailedRetryable),
        "failed_final" => Ok(IdempotencyState::FailedFinal),
        other => Err(format!("unknown_idempotency_state:{other}")),
    }
}

fn outbox_state(value: &str) -> Result<OutboxState, String> {
    match value {
        "pending" => Ok(OutboxState::Pending),
        "sent" => Ok(OutboxState::Sent),
        "verified" => Ok(OutboxState::Verified),
        "failed_retryable" => Ok(OutboxState::FailedRetryable),
        "failed_final" => Ok(OutboxState::FailedFinal),
        "cancelled" => Ok(OutboxState::Cancelled),
        other => Err(format!("unknown_outbox_state:{other}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shared_user_scenario_matrix_fixture_passes() {
        let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
        let path = manifest_dir.join("../../safety_fixtures/businessaios_user_scenario_matrix_golden.json");
        run_user_scenario_matrix_file(&path).expect("shared user scenario matrix should pass");
    }

    #[test]
    fn user_scenario_matrix_blocks_missing_evidence() {
        let case = UserScenarioCase {
            name: "missing_evidence".to_string(),
            scenario: "cli_run".to_string(),
            input: UserScenarioInput {
                entrypoint: "cli".to_string(),
                tenant_id: "tenant-a".to_string(),
                business_id: "business-a".to_string(),
                binding_tenant_id: "tenant-a".to_string(),
                goal: "get 10 clients".to_string(),
                requested_outbound: 10,
                approved_limit: 10,
                idempotency_from: "new".to_string(),
                idempotency_to: "reserved".to_string(),
                outbox_from: "pending".to_string(),
                outbox_to: "sent".to_string(),
                evidence_required: false,
            },
            expected: ExpectedScenarioVerdict {
                allowed: false,
                reason: "evidence_required".to_string(),
            },
        };
        assert_eq!(
            evaluate_user_scenario_case(&case).map(|item| verdict_reason(&item)),
            Ok("evidence_required".to_string())
        );
    }
}
