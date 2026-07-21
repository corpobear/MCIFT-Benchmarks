param(
    [string]$MciftRepo = "../../MCIFT"
)

$resolved = Resolve-Path -LiteralPath $MciftRepo -ErrorAction Stop
python -m pip install -e $resolved.Path
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -c "import mcift; from packaging.version import Version; from mcift.profiles import IMS_SIX_GATE_PROFILE_ID, VIBRATION_PROFILE_ID; assert Version(mcift.__version__) >= Version('0.1.0.dev3'); assert IMS_SIX_GATE_PROFILE_ID == 'mcift.gates.ims-six-gate.v1'; assert VIBRATION_PROFILE_ID == 'mcift.exchange.vibration.v1'; print(mcift.__version__)"
