use pyo3::prelude::*;

#[pyfunction]
fn rms(xs: Vec<f64>) -> PyResult<f64> {
    if xs.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("empty sample"));
    }
    let s: f64 = xs.iter().map(|x| x * x).sum();
    Ok((s / xs.len() as f64).sqrt())
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rms, m)?)?;
    Ok(())
}
