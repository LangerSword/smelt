use pyo3::prelude::*;

// NOTE: this fixture is correct for all in-domain inputs, but the edge battery
// includes (a = i64::MIN, b = -1), where Python's floor division returns 2**63 —
// a value beyond i64. An i64 rewrite cannot match it, so this candidate is
// expected to be REJECTED on that edge. Kept as the documented example of the
// i64 domain gap (see README "Honest limits"). The accepted multi-param proof
// is clamp_all_correct.rs.
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
