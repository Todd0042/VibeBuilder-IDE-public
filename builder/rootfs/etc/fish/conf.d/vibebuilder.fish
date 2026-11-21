# New shell tabs in the IDE greet you with fastfetch (agent tabs and nested shells don't).
set -g fish_greeting
if status is-interactive; and test "$VB_TERMINAL_KIND" = shell; and not set -q VB_GREETED
    set -gx VB_GREETED 1
    fastfetch -c /etc/vibebuilder/fastfetch.jsonc 2>/dev/null
end
