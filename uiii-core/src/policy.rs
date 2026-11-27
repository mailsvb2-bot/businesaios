use crate::{Scope, Interval};
use std::collections::BTreeSet;

#[derive(Clone, Debug)]
pub struct Grant { pub id: String, pub scope: Scope, pub operations: BTreeSet<String>, pub valid: Interval,
    pub revoked_at: Option<i64>, pub destinations: BTreeSet<String> }
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Verdict { Allow, Deny, Indeterminate }
pub fn check(grant: Option<&Grant>, scope: &Scope, operation: &str, destination: &str, at: i64) -> Verdict {
    let g = match grant { Some(g) => g, None => return Verdict::Indeterminate };
    if scope.validate().is_err() || &g.scope != scope || !g.valid.contains(at)
        || g.revoked_at.map_or(false, |t| t <= at) || !g.operations.contains(operation)
        || !g.destinations.contains(destination) { return Verdict::Deny; }
    Verdict::Allow
}
/// Data-use permission never substitutes the consumer's business-action guard.
pub fn can_use_data(data: Verdict, consumer_authorized: bool, fresh: bool, suppressed: bool) -> bool {
    data == Verdict::Allow && consumer_authorized && fresh && !suppressed
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ErasureStage { Restricted, Purging, AwaitingRecipients, Complete }
#[derive(Clone, Debug)]
pub struct Erasure { pub scope: Scope, pub subject: String, pub stage: ErasureStage,
    pub stores_pending: BTreeSet<String>, pub recipients_pending: BTreeSet<String> }
impl Erasure {
    pub fn begin(scope: Scope, subject: String, stores: BTreeSet<String>, recipients: BTreeSet<String>) -> Result<Self, &'static str> {
        scope.validate()?; if subject.is_empty() { return Err("subject_required"); }
        Ok(Self { scope, subject, stage: ErasureStage::Restricted, stores_pending: stores, recipients_pending: recipients })
    }
    pub fn confirm_store(&mut self, store: &str) { self.stores_pending.remove(store); self.advance(); }
    pub fn confirm_recipient(&mut self, recipient: &str) { self.recipients_pending.remove(recipient); self.advance(); }
    fn advance(&mut self) { self.stage = if !self.stores_pending.is_empty() { ErasureStage::Purging }
        else if !self.recipients_pending.is_empty() { ErasureStage::AwaitingRecipients } else { ErasureStage::Complete }; }
}
