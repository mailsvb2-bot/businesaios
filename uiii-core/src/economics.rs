use std::collections::BTreeMap;
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Reservation { pub maximum: u64, pub committed: Option<u64> }
#[derive(Default)]
pub struct Budget { pub limit: u64, operations: BTreeMap<String,Reservation> }
impl Budget {
    pub fn reserved_or_spent(&self) -> Result<u64,&'static str> {
        self.operations.values().try_fold(0u64,|sum,r| sum.checked_add(r.committed.unwrap_or(r.maximum)).ok_or("overflow"))
    }
    pub fn reserve(&mut self,id: &str,maximum: u64) -> Result<bool,&'static str> {
        if id.is_empty() { return Err("operation_id_required"); }
        if let Some(r)=self.operations.get(id) { return if r.maximum==maximum {Ok(false)} else {Err("operation_conflict")}; }
        if self.reserved_or_spent()?.checked_add(maximum).ok_or("overflow")? > self.limit {return Err("budget_exceeded");}
        self.operations.insert(id.into(),Reservation{maximum,committed:None}); Ok(true)
    }
    pub fn commit(&mut self,id: &str,amount: u64) -> Result<(),&'static str> {
        let r=self.operations.get_mut(id).ok_or("reservation_missing")?;
        if amount>r.maximum {return Err("reservation_exceeded");}
        if r.committed.map_or(false,|old|old!=amount) {return Err("commit_conflict");}
        r.committed=Some(amount); Ok(())
    }
}
