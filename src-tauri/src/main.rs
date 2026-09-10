// Keep the development console, but do not allocate one for the Windows GUI app.
#![cfg_attr(all(not(debug_assertions), target_os = "windows"), windows_subsystem = "windows")]

fn main() {
    wisetodo_lib::run();
}
