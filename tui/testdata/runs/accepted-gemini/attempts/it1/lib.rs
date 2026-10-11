use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    if text.is_empty() {
        return String::new();
    }

    let mut out = String::new();
    let mut chars = text.chars();
    
    if let Some(mut prev) = chars.next() {
        let mut count = 1;
        
        for ch in chars {
            if ch == prev {
                count += 1;
            } else {
                out.push(prev);
                out.push_str(&count.to_string());
                prev = ch;
                count = 1;
            }
        }
        out.push(prev);
        out.push_str(&count.to_string());
    }
    
    out
}

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rle_encode, m)?)?;
    Ok(())
}