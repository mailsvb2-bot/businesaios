//! Source-independent UIII domain algorithms. No business decisions or external effects.
//! In-memory objects are calculation/replay state, not a production durable store.
pub mod evidence;
pub mod identity;
pub mod policy;
pub mod sources;
pub mod analytics;
pub mod subscriptions;
pub mod economics;

#[derive(Clone, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub struct Scope {
    pub tenant: String,
    pub business: String,
    pub controller: String,
    pub purpose: String,
    pub region: String,
}
impl Scope {
    pub fn validate(&self) -> Result<(), &'static str> {
        if [&self.tenant, &self.business, &self.controller, &self.purpose, &self.region]
            .iter().any(|x| x.trim().is_empty() || x.len() > 200 || x.chars().any(char::is_control)) {
            Err("invalid_scope")
        } else { Ok(()) }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Knowledge { Unknown, NotObservable, Denied, KnownZero, Observed }

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Interval { pub from: i64, pub until: i64 }
impl Interval {
    pub fn validate(&self) -> Result<(), &'static str> {
        if self.from >= self.until { Err("invalid_interval") } else { Ok(()) }
    }
    pub fn contains(&self, t: i64) -> bool { self.from <= t && t < self.until }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;
    fn scope() -> Scope { Scope{tenant:"t".into(),business:"b".into(),controller:"c".into(),purpose:"crm".into(),region:"RU".into()} }
    fn record(id: &str, parents: &[&str]) -> evidence::Evidence {
        evidence::Evidence{id:id.into(),claim:evidence::Claim::Observation{subject:id.into()},scope:scope(),source_record:format!("source:{id}"),upstream_origin:"origin".into(),
          rule_version:"v1".into(),revision:1,valid:Interval{from:0,until:100},recorded_at:1,observed_at:Some(0),
          parents:parents.iter().map(|v|v.to_string()).collect()}
    }
    #[test] fn retraction_propagates_but_preserves_as_known_history() {
        let mut g=evidence::Graph::default();g.insert(record("a",&[])).unwrap();g.insert(record("b",&["a"])).unwrap();
        assert!(g.accepted_at("b",&scope(),10,10));
        assert_eq!(g.retract("a",&scope(),20).unwrap(),vec!["a".to_string(),"b".to_string()]);
        assert!(g.accepted_at("b",&scope(),10,10));assert!(!g.accepted_at("b",&scope(),10,30));
    }
    #[test] fn missing_parent_scope_and_duplicate_origin() {
        let mut g=evidence::Graph::default();assert!(g.insert(record("b",&["missing"])).is_err());
        g.insert(record("a",&[])).unwrap();g.insert(record("b",&[])).unwrap();
        assert_eq!(g.independent_origins(&["a".into(),"b".into()],&scope()).unwrap(),1);
        let mut foreign=scope();foreign.business="other".into();assert!(!g.accepted_at("a",&foreign,10,10));
    }
    #[test] fn contact_control_never_means_same_person() {
        let mut g=evidence::Graph::default();
        let mut proof=record("a",&[]);
        proof.claim=evidence::Claim::Relation{left:"x".into(),right:"y".into(),kind:evidence::ClaimKind::ContactControl};
        g.insert(proof).unwrap();
        let l=identity::Link{left:"x".into(),right:"y".into(),relation:identity::Relation::ControlsContactAtTime,scope:scope(),evidence:"a".into()};
        assert_eq!(identity::resolve(&l,&[],&g,10,10),identity::Resolution::CandidateOnly);
    }
    #[test] fn playback_seek_and_overlap() {
        let p=sources::Playback{duration_ms:100,watched:vec![(0,10),(5,20),(99,100)]};assert_eq!(p.watched_ms(),21);
    }
    #[test] fn deny_data_use_does_not_disable_existing_independent_actions() {
        let grant=policy::Grant{id:"g".into(),scope:scope(),operations:["export".into()].into_iter().collect(),
          valid:Interval{from:0,until:100},revoked_at:Some(20),destinations:["ba".into()].into_iter().collect()};
        assert_eq!(policy::check(Some(&grant),&scope(),"export","ba",20),policy::Verdict::Deny);
        assert!(!policy::can_use_data(policy::Verdict::Allow,false,true,false));
    }
    #[test] fn erasure_needs_all_receipts() {
        let mut e=policy::Erasure::begin(scope(),"opaque".into(),["db".into()].into_iter().collect(),["ba".into()].into_iter().collect()).unwrap();
        e.confirm_store("db");assert_eq!(e.stage,policy::ErasureStage::AwaitingRecipients);
        e.confirm_recipient("ba");assert_eq!(e.stage,policy::ErasureStage::Complete);
    }
    #[test] fn reservation_idempotency_and_budget_limit() {
        let mut b=economics::Budget::default();b.limit=100;
        assert_eq!(b.reserve("a",80),Ok(true));assert_eq!(b.reserve("a",80),Ok(false));assert!(b.reserve("b",21).is_err());
        b.commit("a",50).unwrap();assert_eq!(b.reserve("b",50),Ok(true));assert!(b.commit("a",51).is_err());
    }
    #[test] fn bounded_filter() {
        let s=subscriptions::Signal{scope:scope(),kind:"call".into(),observed_at:10,score:None,retracted:false};
        assert_eq!(subscriptions::Predicate::FreshWithin(10).matches(&s,&scope(),20),Ok(true));
        assert_eq!(subscriptions::Predicate::All(vec![subscriptions::Predicate::Kind("call".into());130]).matches(&s,&scope(),20),Err("filter_budget_exceeded"));
        let _ = BTreeSet::<String>::new();
    }
}

#[cfg(test)]
mod proof_binding_tests {
    use super::*;
    #[test]
    fn an_observation_does_not_prove_an_unrelated_identity_link() {
        let scope=Scope{tenant:"t".into(),business:"b".into(),controller:"c".into(),purpose:"crm".into(),region:"RU".into()};
        let mut graph=evidence::Graph::default();
        graph.insert(evidence::Evidence{id:"e".into(),claim:evidence::Claim::Observation{subject:"product".into()},
            scope:scope.clone(),source_record:"source".into(),upstream_origin:"origin".into(),rule_version:"v1".into(),
            revision:1,valid:Interval{from:0,until:100},recorded_at:1,observed_at:Some(0),parents:Default::default()}).unwrap();
        let link=identity::Link{left:"customer-a".into(),right:"customer-b".into(),relation:identity::Relation::SameAccount,
            scope,evidence:"e".into()};
        assert_eq!(identity::resolve(&link,&[],&graph,10,10),identity::Resolution::Unknown);
    }
}
