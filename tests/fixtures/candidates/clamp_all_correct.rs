use pyo3::prelude::*;

#[pyfunction]
fn clamp_all(values: Vec<i64>, lo: i64, hi: i64) -> Vec<i64> {
    values.iter().map(|v| (*v).max(lo).min(hi)).collect()
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(clamp_all, m)?)?;
    Ok(())
}
