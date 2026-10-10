use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] {
            j += 1;
        }
        out.push(chars[i]);
        out.push_str(&(j - i).to_string());
        i = j;
    }
    out
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rle_encode, m)?)?;
    Ok(())
}
