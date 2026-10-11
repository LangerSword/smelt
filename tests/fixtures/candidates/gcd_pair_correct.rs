use pyo3::prelude::*;

#[pyfunction]
fn gcd_pair(p: (i64, i64)) -> i64 {
    let (x, y) = p;
    let (mut a, mut b) = (x.abs(), y.abs());
    while b != 0 {
        let r = a % b;
        a = b;
        b = r;
    }
    a
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(gcd_pair, m)?)?;
    Ok(())
}
