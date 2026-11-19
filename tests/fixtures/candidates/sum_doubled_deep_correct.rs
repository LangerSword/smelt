use pyo3::prelude::*;

#[pyfunction]
fn sum_doubled_deep(xs: Vec<i64>) -> i64 {
    let s: i64 = xs.iter().map(|x| x * 2).sum();
    s + 1
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_doubled_deep, m)?)?;
    Ok(())
}
