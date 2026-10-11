use pyo3::prelude::*;

#[pyfunction]
fn manhattan(p: (i64, i64)) -> i64 {
    p.0.abs() + p.1.abs()
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(manhattan, m)?)?;
    Ok(())
}
