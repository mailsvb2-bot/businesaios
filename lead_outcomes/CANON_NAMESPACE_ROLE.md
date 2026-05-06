# lead_outcomes namespace role

`lead_outcomes/` is the canonical mutable lead-outcome state surface.

It owns:
- lead outcome registry truth
- thin field trackers for canonical outcome fields
- outcome mutation primitives
- outcome timeline append semantics
- outcome explanation for stored outcome rows

Must NOT contain:
- second attribution provenance truth
- touchpoint modeling ownership
- campaign credit allocation engines
- multi-touch or first/last-touch policy truth
- second revenue-source explanation layer separate from stored outcome state
