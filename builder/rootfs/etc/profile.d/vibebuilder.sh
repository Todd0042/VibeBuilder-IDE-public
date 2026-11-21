# VibeBuilder builder environment (login shells; fish inherits it from the bash that starts it).
export RUSTUP_HOME=/opt/rustup
export CARGO_HOME="$HOME/.cargo"
export GOPATH="$HOME/go"
export NPM_CONFIG_PREFIX="$HOME/.npm-global"
export PNPM_HOME="$HOME/.local/share/pnpm"
export ANDROID_HOME=/opt/android-sdk
export ANDROID_SDK_ROOT=/opt/android-sdk
export ANDROID_NDK_HOME=/opt/android-sdk/ndk/27.2.12479018
export JAVA_HOME=/usr/lib/jvm/default
export UV_CACHE_DIR="$HOME/.cache/uv"
export EDITOR=nano
export PATH="$HOME/.local/bin:$NPM_CONFIG_PREFIX/bin:$PNPM_HOME:$CARGO_HOME/bin:$GOPATH/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
if [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then . "$HOME/.nix-profile/etc/profile.d/nix.sh"; fi
