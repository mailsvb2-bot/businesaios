use crate::Scope;
#[derive(Clone, Debug)]
pub enum Predicate { Kind(String), FreshWithin(i64), MinScore(u8), All(Vec<Predicate>), Any(Vec<Predicate>) }
pub struct Signal { pub scope: Scope, pub kind: String, pub observed_at: i64, pub score: Option<u8>, pub retracted: bool }
impl Predicate {
    fn evaluate(&self, s: &Signal, now: i64, budget: &mut usize, depth: usize) -> Result<bool,&'static str> {
        if *budget == 0 || depth > 16 { return Err("filter_budget_exceeded"); } *budget-=1;
        match self {
            Self::Kind(k)=>Ok(&s.kind==k),
            Self::FreshWithin(max)=>Ok(*max>=0 && now>=s.observed_at && now.saturating_sub(s.observed_at)<=*max),
            Self::MinScore(min)=>Ok(*min<=100 && s.score.map_or(false,|v| v<=100 && v>=*min)),
            Self::All(v)=>{ let mut hit=true; for p in v { hit &= p.evaluate(s,now,budget,depth+1)?; } Ok(hit) },
            Self::Any(v)=>{ let mut hit=false; for p in v { hit |= p.evaluate(s,now,budget,depth+1)?; } Ok(hit) },
        }
    }
    pub fn matches(&self, signal: &Signal, scope: &Scope, now: i64) -> Result<bool,&'static str> {
        if &signal.scope!=scope || signal.retracted { return Ok(false); }
        self.evaluate(signal,now,&mut 128usize,0)
    }
}
