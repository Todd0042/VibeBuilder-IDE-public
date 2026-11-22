fn main() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("android") {
        // Android 15+ 16 KB page-size devices require 16 KB (0x4000) ELF PT_LOAD alignment.
        println!("cargo:rustc-cdylib-link-arg=-Wl,-z,max-page-size=16384");
        println!("cargo:rustc-cdylib-link-arg=-Wl,-z,common-page-size=16384");
    }
    tauri_build::build()
}
