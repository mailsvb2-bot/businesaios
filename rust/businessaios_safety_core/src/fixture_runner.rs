use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

use crate::{
    validate_blast_radius, validate_budget, validate_idempotency_transition, validate_outbox_transition,
    validate_refund, validate_tenant_scope, IdempotencyState, MoneyMinor, OutboxState, SafetyVerdict,
    TenantScope,
};

#[derive(Debug, Deserialize)]
pub struct FixturePayload {
    pub version: String,
    pub cases: Vec<FixtureCase>,
}

#[derive(Debug, Deserialize)]
pub struct FixtureCase {
    pub name: String,
    pub kind: String,
    pub input: serde_json::Value,
    pub expected: ExpectedVerdict,
}

#[derive(Debug, Deserialize)]
pub struct ExpectedVerdict {
    pub allowed: bool,
    pub reason: String,
}

#[derive(Debug, Serialize)]
pub struct FixtureRunReport {
    pub version: String,
    pub passed: bool,
    pub cases: Vec<FixtureCaseReport>,
}

#[derive(Debug, Serialize)]
pub struct FixtureCaseReport {
    pub name: String,
    pub kind: String,
    pub allowed: bool,
    pub reason: String,
    pub expected_allowed: bool,
    pub expected_reason: String,
    pub passed: bool,
}

pub fn load_fixture_payload(path: &Path) -> Result<FixturePayload, String> {
    let text = fs::read_to_string(path).map_err(|err| format!("fixture_read_failed:{err}"))?;
    let payload: FixturePayload = serde_json::from_str(&text).map_err(|err| format!("fixture_parse_failed:{err}"))?;
    if payload.version != "businessaios_safety_core_golden.v1" {
        return Err(format!("fixture_version_mismatch:{}", payload.version));
    }
    Ok(payload)
}

pub fn run_fixture_file(path: &Path) -> Result<(), String> {
    let report = run_fixture_report(path)?;
    if !report.passed {
        let first = report
            .cases
            .iter()
            .find(|item| !item.passed)
            .map(|item| format!("{}: expected allowed={} reason={} got allowed={} reason={}", item.name, item.expected_allowed, item.expected_reason, item.allowed, item.reason))
            .unwrap_or_else(|| "unknown fixture failure".to_string());
        return Err(format!("fixture_case_failed:{first}"));
    }
    Ok(())
}

pub fn run_fixture_report(path: &Path) -> Result<FixtureRunReport, String> {
    let payload = load_fixture_payload(path)?;
    let mut cases = Vec::with_capacity(payload.cases.len());
    let mut passed = true;
    for case in payload.cases.iter() {
        let actual = evaluate_case(case)?;
        let allowed = matches!(actual, SafetyVerdict::Allow);
        let reason = verdict_reason(&actual);
        let case_passed = allowed == case.expected.allowed && reason == case.expected.reason;
        passed = passed && case_passed;
        cases.push(FixtureCaseReport {
            name: case.name.clone(),
            kind: case.kind.clone(),
            allowed,
            reason,
            expected_allowed: case.expected.allowed,
            expected_reason: case.expected.reason.clone(),
            passed: case_passed,
        });
    }
    Ok(FixtureRunReport { version: payload.version, passed, cases })
}

pub fn evaluate_case(case: &FixtureCase) -> Result<SafetyVerdict, String> {
    match case.kind.as_str() {
        "tenant_scope" => Ok(validate_tenant_scope(TenantScope {
            tenant_id: required_str(&case.input, "tenant_id")?,
            business_id: required_str(&case.input, "business_id")?,
            binding_tenant_id: required_str(&case.input, "binding_tenant_id")?,
            allow_global_fallback: optional_bool(&case.input, "allow_global_fallback"),
        })),
        "budget" => {
            let estimated_minor = required_i64(&case.input, "estimated_minor")?;
            let limit_minor = required_i64(&case.input, "limit_minor")?;
            let currency = required_owned_str(&case.input, "currency")?;
            let limit_currency = optional_owned_str(&case.input, "limit_currency").unwrap_or_else(|| currency.clone());
            Ok(validate_budget(
                MoneyMinor { amount_minor: estimated_minor, currency: leak_string(currency) },
                MoneyMinor { amount_minor: limit_minor, currency: leak_string(limit_currency) },
            ))
        }
        "refund" => {
            let captured_minor = required_i64(&case.input, "captured_minor")?;
            let refund_minor = required_i64(&case.input, "refund_minor")?;
            let currency = required_owned_str(&case.input, "currency")?;
            Ok(validate_refund(
                MoneyMinor { amount_minor: captured_minor, currency: leak_string(currency.clone()) },
                MoneyMinor { amount_minor: refund_minor, currency: leak_string(currency) },
            ))
        }
        "blast_radius" => Ok(validate_blast_radius(
            required_u64(&case.input, "requested_outbound")?,
            required_u64(&case.input, "approved_limit")?,
        )),
        "idempotency_transition" => Ok(validate_idempotency_transition(
            idempotency_state(required_str(&case.input, "from")?)?,
            idempotency_state(required_str(&case.input, "to")?)?,
        )),
        "outbox_transition" => Ok(validate_outbox_transition(
            outbox_state(required_str(&case.input, "from")?)?,
            outbox_state(required_str(&case.input, "to")?)?,
        )),
        other => Err(format!("unknown_fixture_kind:{other}")),
    }
}

pub fn verdict_reason(verdict: &SafetyVerdict) -> String {
    match verdict {
        SafetyVerdict::Allow => "allow".to_string(),
        SafetyVerdict::Deny { reason } => reason.to_string(),
    }
}

fn required_str<'a>(value: &'a serde_json::Value, key: &str) -> Result<&'a str, String> {
    value.get(key).and_then(|item| item.as_str()).ok_or_else(|| format!("fixture_missing_str:{key}"))
}

fn required_owned_str(value: &serde_json::Value, key: &str) -> Result<String, String> {
    Ok(required_str(value, key)?.to_string())
}

fn optional_owned_str(value: &serde_json::Value, key: &str) -> Option<String> {
    value.get(key).and_then(|item| item.as_str()).map(|item| item.to_string())
}

fn optional_bool(value: &serde_json::Value, key: &str) -> bool {
    value.get(key).and_then(|item| item.as_bool()).unwrap_or(false)
}

fn required_i64(value: &serde_json::Value, key: &str) -> Result<i64, String> {
    value.get(key).and_then(|item| item.as_i64()).ok_or_else(|| format!("fixture_missing_i64:{key}"))
}

fn required_u64(value: &serde_json::Value, key: &str) -> Result<u64, String> {
    value.get(key).and_then(|item| item.as_u64()).ok_or_else(|| format!("fixture_missing_u64:{key}"))
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

fn leak_string(value: String) -> &'static str {
    Box::leak(value.into_boxed_str())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shared_golden_fixture_file_passes() {
        let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
        let path = manifest_dir.join("../../safety_fixtures/businessaios_safety_core_golden.json");
        run_fixture_file(&path).expect("shared fixture file should match Rust safety core");
    }

    #[test]
    fn shared_golden_fixture_report_is_machine_readable() {
        let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
        let path = manifest_dir.join("../../safety_fixtures/businessaios_safety_core_golden.json");
        let report = run_fixture_report(&path).expect("shared fixture report should build");
        assert!(report.passed);
        assert!(!report.cases.is_empty());
    }
}
