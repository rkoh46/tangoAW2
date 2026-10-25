//! `wait_until` conditions: a JSON object matched against the `state` answer.
//!
//! - `{"phase":"battle","active_army":2}`: every key must hold. A key is a path into the state (`armies.0.funds`,
//!   `rules.fog`, `map.name`); a plain value means equal.
//! - `{"day":{"gte":3}}`, `{"army":{"in":[1,2]}}`: an object of tests, all of which must hold: `eq`, `ne`, `gt`, `gte`,
//!   `lt`, `lte`, `in`, `nin`, `contains` (a string or an array contains the value), `exists`.
//! - `{"any":[c1,c2]}`, `{"all":[c1,c2]}`, `{"not":c}` combine conditions.
//! - Two more cues come from the units: `{"unit_at":[x,y]}` holds when a unit stands there, `{"no_unit_at":[x,y]}`
//!   when none does.

use serde_json::Value;

/// The value at a dotted path (array elements by number), if any.
pub fn lookup<'a>(state: &'a Value, path: &str) -> Option<&'a Value> {
    let mut v = state;
    for part in path.split('.') {
        v = match v {
            Value::Object(m) => m.get(part)?,
            Value::Array(a) => a.get(part.parse::<usize>().ok()?)?,
            _ => return None,
        };
    }
    Some(v)
}

fn num(v: &Value) -> Option<f64> {
    v.as_f64()
}

fn test(have: Option<&Value>, op: &str, want: &Value) -> Result<bool, String> {
    let cmp = |f: fn(f64, f64) -> bool| -> bool {
        match (have.and_then(num), num(want)) {
            (Some(a), Some(b)) => f(a, b),
            _ => false,
        }
    };
    Ok(match op {
        "eq" => have == Some(want),
        "ne" => have != Some(want),
        "gt" => cmp(|a, b| a > b),
        "gte" => cmp(|a, b| a >= b),
        "lt" => cmp(|a, b| a < b),
        "lte" => cmp(|a, b| a <= b),
        "in" => want
            .as_array()
            .ok_or("`in` needs an array")?
            .iter()
            .any(|w| Some(w) == have),
        "nin" => !want
            .as_array()
            .ok_or("`nin` needs an array")?
            .iter()
            .any(|w| Some(w) == have),
        "contains" => match have {
            Some(Value::String(s)) => want.as_str().is_some_and(|w| s.contains(w)),
            Some(Value::Array(a)) => a.iter().any(|x| x == want),
            _ => false,
        },
        "exists" => have.is_some() == want.as_bool().unwrap_or(true),
        other => return Err(format!("unknown test `{other}`")),
    })
}

fn unit_at(state: &Value, cell: &Value) -> Result<bool, String> {
    let c = cell.as_array().filter(|c| c.len() == 2).ok_or("a cell is [x, y]")?;
    let (x, y) = (c[0].as_i64(), c[1].as_i64());
    Ok(state["units"].as_array().is_some_and(|us| {
        us.iter()
            .any(|u| u["x"].as_i64() == x && u["y"].as_i64() == y && u["carried"] != Value::Bool(true))
    }))
}

/// Whether the state satisfies the condition; `Err` for a malformed condition.
pub fn matches(state: &Value, cond: &Value) -> Result<bool, String> {
    let Some(obj) = cond.as_object() else {
        return Err("a condition is a JSON object".into());
    };
    for (key, want) in obj {
        let ok = match key.as_str() {
            "all" => {
                let mut all = true;
                for c in want.as_array().ok_or("`all` needs an array")? {
                    all &= matches(state, c)?;
                }
                all
            }
            "any" => {
                let mut any = false;
                for c in want.as_array().ok_or("`any` needs an array")? {
                    any |= matches(state, c)?;
                }
                any
            }
            "not" => !matches(state, want)?,
            "unit_at" => unit_at(state, want)?,
            "no_unit_at" => !unit_at(state, want)?,
            path => {
                let have = lookup(state, path);
                match want {
                    Value::Object(tests) if !tests.is_empty() && tests.keys().all(|k| TESTS.contains(&k.as_str())) => {
                        let mut all = true;
                        for (op, w) in tests {
                            all &= test(have, op, w)?;
                        }
                        all
                    }
                    w => have == Some(w),
                }
            }
        };
        if !ok {
            return Ok(false);
        }
    }
    Ok(true)
}

const TESTS: [&str; 10] = ["exists", "eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains"];

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn state() -> Value {
        json!({"phase":"battle","active_army":2,"day":3,"rules":{"fog":false},"armies":[{"funds":1000},{"funds":7000}],
               "units":[{"x":1,"y":2,"carried":false},{"x":5,"y":5,"carried":true}],"map":{"name":"Ball Islands"}})
    }

    #[test]
    fn plain_equality_and_paths() {
        assert!(matches(&state(), &json!({"phase":"battle","active_army":2})).unwrap());
        assert!(!matches(&state(), &json!({"phase":"battle","active_army":1})).unwrap());
        assert!(matches(&state(), &json!({"rules.fog":false,"armies.1.funds":7000})).unwrap());
        assert!(!matches(&state(), &json!({"nope":1})).unwrap());
    }

    #[test]
    fn tests_and_combinators() {
        assert!(matches(&state(), &json!({"day":{"gte":3,"lt":4}})).unwrap());
        assert!(!matches(&state(), &json!({"day":{"gt":3}})).unwrap());
        assert!(matches(&state(), &json!({"active_army":{"in":[1,2]}})).unwrap());
        assert!(matches(&state(), &json!({"map.name":{"contains":"Island"}})).unwrap());
        assert!(matches(&state(), &json!({"any":[{"phase":"title"},{"phase":"battle"}]})).unwrap());
        assert!(matches(&state(), &json!({"not":{"phase":"title"}})).unwrap());
        assert!(matches(&state(), &json!({"unit_at":[1,2],"no_unit_at":[5,5]})).unwrap());
    }

    #[test]
    fn malformed_conditions_are_errors() {
        assert!(matches(&state(), &json!(3)).is_err());
        assert!(matches(&state(), &json!({"all":3})).is_err());
        assert!(matches(&state(), &json!({"day":{"in":3}})).is_err());
    }
}
