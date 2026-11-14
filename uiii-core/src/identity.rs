use crate::{Scope, evidence::{Graph, ClaimKind}};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Relation { SameAccount, ControlsContactAtTime, ObservedWith, CannotLink }
#[derive(Clone, Debug)]
pub struct Link {
    pub left: String, pub right: String, pub relation: Relation,
    pub scope: Scope, pub evidence: String,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Resolution { SameAccount, CandidateOnly, Conflict, Unknown }

fn claim_kind(relation: &Relation) -> ClaimKind {
    match relation {
        Relation::SameAccount => ClaimKind::SameAccount,
        Relation::ControlsContactAtTime => ClaimKind::ContactControl,
        Relation::ObservedWith => ClaimKind::ObservedWith,
        Relation::CannotLink => ClaimKind::CannotLink,
    }
}

pub fn resolve(link: &Link, negative: &[Link], graph: &Graph, at: i64, known_at: i64) -> Resolution {
    if !graph.supports_relation(&link.evidence, &link.scope, &link.left, &link.right, &claim_kind(&link.relation)) {
        return Resolution::Unknown;
    }
    if !graph.accepted_at(&link.evidence, &link.scope, at, known_at) { return Resolution::Unknown; }
    if negative.iter().any(|n| n.scope == link.scope && n.relation == Relation::CannotLink
        && ((n.left == link.left && n.right == link.right) || (n.right == link.left && n.left == link.right))
        && graph.supports_relation(&n.evidence, &n.scope, &n.left, &n.right, &ClaimKind::CannotLink)
        && graph.accepted_at(&n.evidence, &n.scope, at, known_at)) { return Resolution::Conflict; }
    match link.relation { Relation::SameAccount => Resolution::SameAccount,
        Relation::CannotLink => Resolution::Conflict, _ => Resolution::CandidateOnly }
}

/// Rebuild UIII clusters after retraction; never mutate canonical CRM identity.
pub fn clusters(links: &[Link], graph: &Graph, scope: &Scope, at: i64, known_at: i64)
    -> BTreeMap<String, BTreeSet<String>> {
    let negatives: Vec<Link> = links.iter().filter(|l| l.relation == Relation::CannotLink).cloned().collect();
    let mut adjacency: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for l in links.iter().filter(|l| &l.scope == scope) {
        adjacency.entry(l.left.clone()).or_default(); adjacency.entry(l.right.clone()).or_default();
        if resolve(l, &negatives, graph, at, known_at) == Resolution::SameAccount {
            adjacency.entry(l.left.clone()).or_default().insert(l.right.clone());
            adjacency.entry(l.right.clone()).or_default().insert(l.left.clone());
        }
    }
    let mut groups = BTreeMap::new(); let mut seen = BTreeSet::new();
    for root in adjacency.keys() {
        if seen.contains(root) { continue; }
        let mut members = BTreeSet::new(); let mut stack = vec![root.clone()];
        while let Some(id) = stack.pop() {
            if !members.insert(id.clone()) { continue; }
            stack.extend(adjacency[&id].iter().cloned());
        }
        // Transitive bridges that include cannot-link must not auto-merge identities.
        let conflict = negatives.iter().any(|n| &n.scope == scope && members.contains(&n.left)
            && members.contains(&n.right)
            && graph.supports_relation(&n.evidence, scope, &n.left, &n.right, &ClaimKind::CannotLink)
            && graph.accepted_at(&n.evidence, scope, at, known_at));
        seen.extend(members.iter().cloned());
        if conflict { for id in members { groups.insert(id.clone(), [id].into_iter().collect()); } }
        else { groups.insert(root.clone(), members); }
    }
    groups
