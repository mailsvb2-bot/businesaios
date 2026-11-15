use crate::{Knowledge, Scope};
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OfferKey { pub variant: String, pub condition: String, pub currency: String, pub unit: String,
    pub region: String, pub terms: String }
#[derive(Clone, Debug)]
pub struct Offer { pub scope: Scope, pub key: OfferKey, pub amount_minor: i64, pub observed_at: i64,
    pub evidence: String, pub stock: Option<u64>, pub knowledge: Knowledge }
pub fn price_delta(a: &Offer,b: &Offer) -> Result<i64,&'static str> {
    if a.scope != b.scope || a.key != b.key { return Err("not_comparable"); }
    if a.evidence.is_empty() || b.evidence.is_empty() || a.amount_minor < 0 || b.amount_minor < 0
        || b.observed_at <= a.observed_at || a.knowledge != Knowledge::Observed || b.knowledge != Knowledge::Observed {
        return Err("invalid_observation");
    }
    b.amount_minor.checked_sub(a.amount_minor).ok_or("arithmetic_overflow")
}
#[derive(Clone, Debug)]
pub struct Calibration { pub samples: usize, pub brier: Option<f64>, pub expected_calibration_error: Option<f64> }
pub fn calibrate(rows: &[(f64,bool)], bins: usize) -> Result<Calibration,&'static str> {
    if bins == 0 || bins > 100 || rows.iter().any(|(p,_)| !p.is_finite() || *p < 0. || *p > 1.) { return Err("invalid_calibration"); }
    if rows.is_empty() { return Ok(Calibration{samples:0,brier:None,expected_calibration_error:None}); }
    let mut counts=vec![0usize;bins]; let mut predicted=vec![0.;bins]; let mut actual=vec![0.;bins]; let mut sum=0.;
    for (p,y) in rows { let target=if *y {1.} else {0.}; let i=((*p*bins as f64) as usize).min(bins-1);
        counts[i]+=1; predicted[i]+=p; actual[i]+=target; sum+=(p-target).powi(2); }
    let mut ece=0.; for i in 0..bins { if counts[i]>0 { ece+=(predicted[i]-actual[i]).abs()/rows.len() as f64; } }
    Ok(Calibration{samples:rows.len(),brier:Some(sum/rows.len() as f64),expected_calibration_error:Some(ece)})
}
/// Descriptive difference only; assignment validity/confounding must be evaluated separately.
pub fn outcome_difference(treatment: &[f64], control: &[f64]) -> Result<f64,&'static str> {
    if treatment.is_empty() || control.is_empty() || treatment.iter().chain(control).any(|v| !v.is_finite()) {
        return Err("insufficient_valid_outcomes"); }
    Ok(treatment.iter().sum::<f64>()/treatment.len() as f64 - control.iter().sum::<f64>()/control.len() as f64)
}
