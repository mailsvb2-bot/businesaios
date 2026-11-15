use crate::Scope;
use std::collections::BTreeSet;
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Granularity { Aggregate, AnonymousSession, Account, VerifiedContact }
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Maturity { Candidate, ContractTested, LiveVerified }
#[derive(Clone, Debug)]
pub struct Capability { pub provider: String, pub name: String, pub scope: Scope, pub granularity: Granularity,
    pub maturity: Maturity, pub live_verified_until: Option<i64>, pub fields: BTreeSet<String>, pub permitted: bool }
impl Capability {
    pub fn require(&self, scope: &Scope, fields: &BTreeSet<String>, personal: bool, at: i64) -> Result<(), &'static str> {
        if &self.scope != scope || !self.permitted { return Err("capability_denied"); }
        if self.maturity != Maturity::LiveVerified || !self.live_verified_until.map_or(false, |t| at < t) {
            return Err("live_capability_unverified");
        }
        if !fields.is_subset(&self.fields) { return Err("field_not_observable"); }
        if personal && matches!(self.granularity, Granularity::Aggregate | Granularity::AnonymousSession) {
            return Err("aggregate_to_person_forbidden");
        }
        Ok(())
    }
}
#[derive(Clone, Debug)]
pub struct Playback { pub duration_ms: u64, pub watched: Vec<(u64,u64)> }
impl Playback {
    /// Union actual play intervals; seeking to the end does not create watched time.
    pub fn watched_ms(&self) -> u64 {
        let mut v: Vec<(u64,u64)> = self.watched.iter().map(|(a,b)| ((*a).min(self.duration_ms),(*b).min(self.duration_ms)))
            .filter(|(a,b)| a < b).collect(); v.sort();
        let mut total = 0; let mut end = 0;
        for (a,b) in v { if b > end { total += b - a.max(end); end = b; } }
        total
    }
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CallState { Started, Completed }
pub fn call_state(events: &[(i64,CallState)]) -> Option<CallState> {
    if events.iter().any(|(_,s)| *s == CallState::Completed) { Some(CallState::Completed) }
    else if events.is_empty() { None } else { Some(CallState::Started) }
}
