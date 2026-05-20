use std::env;
use std::path::Path;

fn main() {
    let mut json = false;
    let mut path = None;
    for arg in env::args().skip(1) {
        if arg == "--json" {
            json = true;
        } else {
            path = Some(arg);
        }
    }
    let path = path.unwrap_or_else(|| "../../safety_fixtures/businessaios_safety_core_golden.json".to_string());
    if json {
        match businessaios_safety_core::fixture_runner::run_fixture_report(Path::new(&path)) {
            Ok(report) => {
                println!("{}", serde_json::to_string(&report).unwrap_or_else(|_| "{\"passed\":false}".to_string()));
                if !report.passed {
                    std::process::exit(1);
                }
            }
            Err(err) => {
                println!("{{\"passed\":false,\"error\":\"{}\"}}", err.replace('"', "'"));
                std::process::exit(1);
            }
        }
        return;
    }
    if let Err(err) = businessaios_safety_core::fixture_runner::run_fixture_file(Path::new(&path)) {
        println!("safety fixture runner failed: {err}");
        std::process::exit(1);
    }
    println!("safety fixture runner passed: {path}");
}
