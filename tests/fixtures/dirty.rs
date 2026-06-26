use std::collections::HashMap;

fn divide(a: i32, b: i32) -> i32 {
    a / b  // no divide-by-zero check
}

fn get_user(users: &HashMap<String, String>, id: String) -> String {
    let query = format!("SELECT * FROM users WHERE id = {}", id);
    users[&id].clone()  // panic if the key does not exist
}

fn main() {
    let password = "super_secret_123";  // hardcoded
    let x = 42;  // unused variable
    println!("done");
}
