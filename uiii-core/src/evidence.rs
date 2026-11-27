use std::collections::{BTreeMap, BTreeSet};
use crate::{Interval, Scope};

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ClaimKind { SameAccount, ContactControl, ObservedWith, CannotLink }
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Claim {
    Observation { subject: String },
    Relation { left: String, right: String, kind: ClaimKind },
}
impl Claim {
    fn valid(&self) -> bool {
        let bounded = |s: &str| !s.trim().is_empty() && s.len() <= 200 && !s.chars().any(char::is_control);
        match self {
            Self::Observation { subject } => bounded(subject),
            Self::Relation { left, right, .. } => bounded(left) && bounded(right),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Evidence {
    pub id: String,
    pub claim: Claim,
    pub scope: Scope,
    pub source_record: String,
    pub upstream_origin: String,
    pub rule_version: String,
    pub revision: u64,
    pub valid: Interval,
    pub recorded_at: i64,
    pub observed_at: Option<i64>,
    pub parents: BTreeSet<String>,
}

#[derive(Clone, Debug, Default)]
pub struct Graph {
    records: BTreeMap<String, Evidence>,
    retracted_at: BTreeMap<String, i64>,
}
impl Graph {
    pub fn insert(&mut self, record: Evidence) -> Result<bool, &'static str> {
        record.scope.validate()?;
        record.valid.validate()?;
        if !record.claim.valid() || record.id.is_empty() || record.source_record.is_empty()
            || record.upstream_origin.is_empty() || record.rule_version.is_empty()
            || record.revision == 0 || record.parents.contains(&record.id) {
            return Err("provenance_required");
        }
        if let Some(old) = self.records.get(&record.id) {
            return if old == &record { Ok(false) } else { Err("evidence_id_conflict") };
        }
        // Parents must already exist; admission makes a cycle impossible.
        for parent in &record.parents {
            let p = self.records.get(parent).ok_or("parent_missing")?;
            if p.scope != record.scope || p.recorded_at > record.recorded_at {
                return Err("parent_scope_or_time_mismatch");
            }
            if self.retracted_at.get(parent).map_or(false, |t| *t <= record.recorded_at) {
                return Err("parent_retracted");
            }
        }
        self.records.insert(record.id.clone(), record);
        Ok(true)
    }
    pub fn supports_relation(&self, id: &str, scope: &Scope, left: &str, right: &str, kind: &ClaimKind) -> bool {
        let r = match self.records.get(id) { Some(r) if &r.scope == scope => r, _ => return false };
        match &r.claim {
            Claim::Relation { left: a, right: b, kind: k } if k == kind => {
                (a == left && b == right) || (matches!(kind, ClaimKind::SameAccount | ClaimKind::CannotLink)
                    && a == right && b == left)
            }
            _ => false,
        }
    }
    pub fn accepted_at(&self, id: &str, scope: &Scope, valid_at: i64, known_at: i64) -> bool {
        let mut pending = vec![id.to_string()];
        let mut seen = BTreeSet::new();
        while let Some(key) = pending.pop() {
            if !seen.insert(key.clone()) { continue; }
            let r = match self.records.get(&key) { Some(r) => r, None => return false };
            if &r.scope != scope || r.recorded_at > known_at || !r.valid.contains(valid_at)
                || self.retracted_at.get(&key).map_or(false, |t| *t <= known_at) { return false; }
            pending.extend(r.parents.iter().cloned());
        }
        true
    }
    pub fn retract(&mut self, id: &str, scope: &Scope, at: i64) -> Result<Vec<String>, &'static str> {
        let r = self.records.get(id).ok_or("evidence_missing")?;
        if &r.scope != scope || at < r.recorded_at { return Err("retraction_scope_or_time"); }
        self.retracted_at.entry(id.into()).and_modify(|v| *v = (*v).min(at)).or_insert(at);
        let mut affected: BTreeSet<String> = [id.to_string()].into_iter().collect();
        loop {
            let before = affected.len();
            for (key, record) in &self.records {
                if record.parents.iter().any(|p| affected.contains(p)) { affected.insert(key.clone()); }
            }
            if before == affected.len() { break; }
        }
        Ok(affected.into_iter().collect())
    }
    pub fn independent_origins(&self, ids: &[String], scope: &Scope) -> Result<usize, &'static str> {
        let mut origins = BTreeSet::new();
        let mut stack = ids.to_vec();
        let mut seen = BTreeSet::new();
        while let Some(id) = stack.pop() {
            if !seen.insert(id.clone()) { continue; }
            let r = self.records.get(&id).ok_or("evidence_missing")?;
            if &r.scope != scope { return Err("scope_mismatch"); }
            if r.parents.is_empty() { origins.insert(r.upstream_origin.clone()); }
            else { stack.extend(r.parents.iter().cloned()); }
        }
        Ok(origins.len())
    }
}
