use std::collections::HashMap;

fn divide(a: i32, b: i32) -> i32 {
    a / b  // pas de vérification division par zéro
}

fn get_user(users: &HashMap<String, String>, id: String) -> String {
    let query = format!("SELECT * FROM users WHERE id = {}", id);
    users[&id].clone()  // panic si la clé n'existe pas
}

fn main() {
    let password = "super_secret_123";  // hardcodé
    let x = 42;  // variable inutilisée
    println!("done");
}