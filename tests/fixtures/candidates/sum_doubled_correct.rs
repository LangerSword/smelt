use pyo3::prelude::*;

#[pyfunction]
fn sum_doubled(xs: Vec<i64>) -> i64 {
    xs.iter().map(|x| x * 2).sum()
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_doubled, m)?)?;
    Ok(())
}
