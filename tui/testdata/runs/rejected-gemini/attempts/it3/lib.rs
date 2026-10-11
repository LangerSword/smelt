use pyo3::prelude::*;

#[pyfunction]
fn linear_score(x: f64) -> f64 {
    ((x * 1.7 + 3.3) * 0.5) - 2.0
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(linear_score, m)?)?;
    Ok(())
}