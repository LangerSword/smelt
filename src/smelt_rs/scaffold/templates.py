"""Pinned scaffold: the known-compiling pyo3 template + golden example.

This is the fix for the #1 observed failure mode (pyo3 API drift): the crate's
Cargo.toml and the module glue are OURS and pinned; the model only fills in the
function body. The golden example below is the exact structure that compiles against
pyo3 =0.29.3 on this machine (verified during the event). The generation prompt
embeds it verbatim.
"""

PYO3_VERSION = "=0.29.3"
CRATE_NAME = "smelt_ext"

CARGO_TOML = f"""[package]
name = "{CRATE_NAME}"
version = "0.1.0"
edition = "2021"

[lib]
name = "{CRATE_NAME}"
crate-type = ["cdylib"]

[dependencies]
pyo3 = {{ version = "{PYO3_VERSION}", features = ["extension-module"] }}
"""

GOLDEN_LIB_RS = """use pyo3::prelude::*;

#[pyfunction]
fn ping() -> i64 {
    42
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ping, m)?)?;
    Ok(())
}
"""
