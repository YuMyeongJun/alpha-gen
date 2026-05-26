# Alpha-Gen ops watch loop for Cursor /loop integration (Windows).
# Emits a fixed sentinel every N seconds (default 5 minutes).

param(
    [int]$IntervalSec = 0
)

if ($IntervalSec -le 0) {
    $envInterval = [Environment]::GetEnvironmentVariable("ALPHA_GEN_WATCH_INTERVAL_SEC")
    if ($envInterval -and [int]::TryParse($envInterval, [ref]$null)) {
        $IntervalSec = [int]$envInterval
    } else {
        $IntervalSec = 300
    }
}

$prompt = 'alpha-gen ops watch: MCP health_check, get_safety_policy, get_worker_status 요약. 이상 시 alpha-gen-incident skill 적용.'

while ($true) {
    Start-Sleep -Seconds $IntervalSec
    $payload = @{ prompt = $prompt } | ConvertTo-Json -Compress
    Write-Output "AGENT_LOOP_TICK_ALPHA_GEN_OPS $payload"
}
