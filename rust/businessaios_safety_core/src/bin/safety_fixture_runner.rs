use std::env;
use std::path::Path;

fn main() {
    let path = env::args()
        .nth(1)
        .unwrap_or_else(|| "../../safety_fixtures/businessaios_safety_core_golden.json".to_string());
    if let Err(err) = businessaios_safety_core::fixture_runner::run_fixture_file(Path::new(&path)) {
        println!("safety fixture runner failed: {err}");
        std::process::exit(1);
    }
    println!("safety fixture runner passed: {path}");
}
