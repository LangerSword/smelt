use pyo3::prelude::*;

#[pyfunction]
fn is_tuple(p: (i64, i64)) -> bool {
    true
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(is_tuple, m)?)?;
    Ok(())
}
