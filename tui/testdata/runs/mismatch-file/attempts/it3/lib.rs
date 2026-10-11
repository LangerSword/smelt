use pyo3::prelude::*;

#[pyfunction]
fn divide(a: i64, b: i64) -> PyResult<i64> {
    if b == 0 {
        return Err(pyo3::exceptions::PyZeroDivisionError::new_err(
            "integer division or modulo by zero",
        ));
    }
    // Python `//` is FLOOR division: adjust Rust's truncating division when the
    // remainder's sign differs from the divisor's (-7 // 2 == -4, not -3).
    let q = a / b;
    let r = a % b;
    let q = if r != 0 && ((r < 0) != (b < 0)) { q - 1 } else { q };
    Ok(q)
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(divide, m)?)?;
    Ok(())
}
