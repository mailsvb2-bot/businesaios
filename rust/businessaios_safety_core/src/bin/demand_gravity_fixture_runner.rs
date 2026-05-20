use serde_json::Value;
use std::env;
use std::fs;
use std::path::Path;

fn main() {
    let path = env::args()
        .nth(1)
        .unwrap_or_else(|| "../../safety_fixtures/demand_gravity_candidate_contract_golden.json".to_string());
    let result = run(Path::new(&path));
    match result {
        Ok(()) => println!("{{\"passed\":true,\"fixture\":\"{}\"}}", path),
        Err(reason) => {
            println!("{{\"passed\":false,\"reason\":\"{}\"}}", reason.replace('"', "'"));
            std::process::exit(1);
        }
    }
}

fn run(path: &Path) -> Result<(), String> {
    let text = fs::read_to_string(path).map_err(|err| format!("read_failed:{err}"))?;
    let payload: Value = serde_json::from_str(&text).map_err(|err| format!("parse_failed:{err}"))?;
    if payload.get("version").and_then(Value::as_str) != Some("demand_gravity_candidate_contract.v1") {
        return Err("version_mismatch".to_string());
    }
    let forbidden = payload
        .get("forbidden_payload_keys")
        .and_then(Value::as_array)
        .ok_or_else(|| "forbidden_keys_missing".to_string())?;
    if forbidden.is_empty() {
        return Err("forbidden_keys_empty".to_string());
    }
    for key in forbidden {
        let key_text = key.as_str().ok_or_else(|| "forbidden_key_not_string".to_string())?;
        if key_text.trim().is_empty() {
            return Err("forbidden_key_empty".to_string());
        }
    }
    let candidate = payload
        .get("valid_candidate")
        .and_then(Value::as_object)
        .ok_or_else(|| "valid_candidate_missing".to_string())?;
    require_str(candidate.get("candidate_id"), "candidate_id")?;
    require_prefix(candidate.get("candidate_id"), "dgc_", "candidate_id_prefix")?;
    require_str(candidate.get("tenant_id"), "tenant_id")?;
    require_array(candidate.get("signal_ids"), "signal_ids")?;
    require_array(candidate.get("evidence_refs"), "evidence_refs")?;
    require_str(candidate.get("idempotency_key"), "idempotency_key")?;
    require_str(candidate.get("correlation_id"), "correlation_id")?;
    if candidate.get("write_mode").and_then(Value::as_str) != Some("advisory_only") {
        return Err("write_mode_must_be_advisory_only".to_string());
    }
    let payload = candidate
        .get("payload")
        .and_then(Value::as_object)
        .ok_or_else(|| "candidate_payload_missing".to_string())?;
    if payload.get("decision_owner").and_then(Value::as_str) != Some("DecisionCore") {
        return Err("decision_owner_required".to_string());
    }
    if payload.get("execution_allowed").and_then(Value::as_bool) != Some(false) {
        return Err("execution_forbidden".to_string());
    }
    for key in forbidden {
        let key_text = key.as_str().unwrap_or_default();
        if contains_key(candidate.get("payload").unwrap_or(&Value::Null), key_text) {
            return Err("decision_payload_forbidden".to_string());
        }
    }
    Ok(())
}

fn require_str(value: Option<&Value>, reason: &str) -> Result<(), String> {
    match value.and_then(Value::as_str) {
        Some(text) if !text.trim().is_empty() => Ok(()),
        _ => Err(format!("{reason}_required")),
    }
}

fn require_prefix(value: Option<&Value>, prefix: &str, reason: &str) -> Result<(), String> {
    let text = value.and_then(Value::as_str).unwrap_or_default();
    if text.starts_with(prefix) { Ok(()) } else { Err(reason.to_string()) }
}

fn require_array(value: Option<&Value>, reason: &str) -> Result<(), String> {
    match value.and_then(Value::as_array) {
        Some(items) if !items.is_empty() => Ok(()),
        _ => Err(format!("{reason}_required")),
    }
}

fn contains_key(value: &Value, forbidden_key: &str) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, item)| key == forbidden_key || contains_key(item, forbidden_key)),
        Value::Array(items) => items.iter().any(|item| contains_key(item, forbidden_key)),
        _ => false,
    }
}
