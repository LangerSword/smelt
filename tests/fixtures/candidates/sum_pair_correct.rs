use pyo3::prelude::*;

#[pyfunction]
fn sum_pair(xs: Vec<i64>) -> (i64, i64) {
    let s: i64 = xs.iter().sum();
    let q: i64 = xs.iter().map(|x| x * x).sum();
    (s, q)
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_pair, m)?)?;
    Ok(())
}
