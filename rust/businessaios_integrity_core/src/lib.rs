//! BusinessAIOS Integrity Auditor v2 core contract.
//!
//! This crate is intentionally a deterministic scanning core placeholder.
//! It must never become a planning brain, policy engine, or autonomous decision maker.
//! Python v1 remains the canonical orchestrator and CI integration layer.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IntegrityFinding {
    pub check_id: String,
    pub severity: String,
    pub path: String,
    pub line: usize,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScanInput {
    pub root: String,
    pub changed_paths: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScanOutput {
    pub findings: Vec<IntegrityFinding>,
}

pub fn scan(_input: ScanInput) -> ScanOutput {
    ScanOutput { findings: Vec::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scan_is_deterministic_for_same_input() {
        let input = ScanInput {
            root: "/repo".to_string(),
            changed_paths: vec![
                "scripts/ci/integrity/auditor.py".to_string(),
                "core/payments/yookassa_webhook.py".to_string(),
            ],
        };

        let first = scan(input.clone());
        let second = scan(input);

        assert_eq!(first, second);
    }

    #[test]
    fn finding_contract_preserves_identity_fields() {
        let finding = IntegrityFinding {
            check_id: "P0_NO_SECOND_BRAIN".to_string(),
            severity: "P0".to_string(),
            path: "runtime/foo.py".to_string(),
            line: 42,
            message: "second brain candidate".to_string(),
        };

        assert_eq!(finding.check_id, "P0_NO_SECOND_BRAIN");
        assert_eq!(finding.severity, "P0");
        assert_eq!(finding.path, "runtime/foo.py");
        assert_eq!(finding.line, 42);
        assert!(finding.message.contains("second brain"));
    }

    #[test]
    fn scan_output_starts_empty_until_rules_are_ported_from_python_v1() {
        let input = ScanInput {
            root: "/repo".to_string(),
            changed_paths: Vec::new(),
        };

        let output = scan(input);

        assert!(output.findings.is_empty());
    }
}
