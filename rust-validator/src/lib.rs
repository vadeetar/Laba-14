use serde::Deserialize;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;

#[derive(Debug, Deserialize)]
struct MatchRecord {
    home_team: Option<String>,
    away_team: Option<String>,
    home_score: Option<i32>,
    away_score: Option<i32>,
    total_goals: Option<i32>,
}

fn validate_record(record: &MatchRecord) -> bool {
    let home = record.home_team.as_deref().unwrap_or("").trim();
    let away = record.away_team.as_deref().unwrap_or("").trim();
    if home.is_empty() || away.is_empty() {
        return false;
    }

    let home_score = record.home_score.unwrap_or(-1);
    let away_score = record.away_score.unwrap_or(-1);
    let total = record.total_goals.unwrap_or(-1);

    if home_score < 0 || away_score < 0 || total < 0 {
        return false;
    }

    home_score + away_score == total
}

#[no_mangle]
pub extern "C" fn validate_match_json(raw: *const c_char) -> i32 {
    if raw.is_null() {
        return 0;
    }
    let c_str = unsafe { CStr::from_ptr(raw) };
    let Ok(text) = c_str.to_str() else {
        return 0;
    };
    let Ok(record) = serde_json::from_str::<MatchRecord>(text) else {
        return 0;
    };
    if validate_record(&record) {
        1
    } else {
        0
    }
}

#[no_mangle]
pub extern "C" fn validator_version() -> *mut c_char {
    CString::new("sports_validator 0.1.0").unwrap().into_raw()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn valid_match() {
        let record = MatchRecord {
            home_team: Some("A".into()),
            away_team: Some("B".into()),
            home_score: Some(2),
            away_score: Some(1),
            total_goals: Some(3),
        };
        assert!(validate_record(&record));
    }
}
