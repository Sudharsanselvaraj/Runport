"""Workspace configuration, JSON Schema validation, and project initialization."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class BudgetConfig(BaseModel):
    """Budget ceilings and pricing verification settings."""
    total_usd: Decimal = Field(default=Decimal("5.00"), description="Total lifetime experiment ceiling in USD")
    per_run_usd: Decimal = Field(default=Decimal("1.00"), description="Maximum spend allowed per single evaluation run in USD")
    per_case_usd: Decimal = Field(default=Decimal("0.05"), description="Maximum spend allowed per individual evaluation case in USD")
    pilot_usd: Decimal = Field(default=Decimal("1.00"), description="Ceiling for initial pilot evaluation in USD")
    require_priced: bool = Field(default=False, description="Fail preflight if model pricing is unknown or unverified")
    retry_buffer_pct: Decimal = Field(default=Decimal("0.05"), description="Buffer allocation for network/rate-limit retries (5%)")

    def to_budget_policy(self):
        from runport.core.config import BudgetPolicy
        return BudgetPolicy(
            total_budget_usd=self.total_usd,
            pilot_budget_usd=self.pilot_usd,
            per_run_ceiling_usd=self.per_run_usd,
            per_case_ceiling_usd=self.per_case_usd,
            require_priced=self.require_priced,
            retry_buffer_pct=self.retry_buffer_pct,
        )


class ApproverConfig(BaseModel):
    """Execution approval model configuration."""
    default_mode: Literal["interactive", "token", "modal"] = Field(
        default="interactive",
        description="Default approval mode for live runs (interactive, token, or modal)",
    )
    token_approver_enabled: bool = Field(
        default=False,
        description="Allow token approver with --approve <plan_fingerprint> (disabled by default)",
    )


class TelemetryConfig(BaseModel):
    """Local privacy and telemetry settings."""
    local_logging: bool = Field(default=True, description="Enable local SQLite append-only event logging")
    redact_secrets: bool = Field(default=True, description="Automatically scrub API keys and auth bearer tokens")
    forbidden_fields: List[str] = Field(
        default_factory=lambda: ["user4", "phone", "email", "ssn", "national_id"],
        description="Field names forbidden from payload ingestion or exports",
    )


class StorageConfig(BaseModel):
    """Database and file output locations."""
    data_dir: Path = Field(default=Path("data"), description="Directory for database and datasets")
    db_filename: str = Field(default="runport.db", description="SQLite WAL database filename")
    reports_dir: Path = Field(default=Path("reports"), description="Directory for trace and report exports")


class TargetConfig(BaseModel):
    """Target configuration entry within the workspace."""
    id: str = Field(description="Unique identifier for the target")
    type: str = Field(description="Target connector type (e.g. openai_compat, openrouter, dify, http_workflow, ollama)")
    endpoint: Optional[str] = Field(default=None, description="HTTP endpoint or base URL")
    model: Optional[str] = Field(default=None, description="Model identifier if applicable")
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom request headers or environment var references")
    options: Dict[str, Any] = Field(default_factory=dict, description="Target-specific execution options")


class WorkspaceConfig(BaseModel):
    """Top-level Runport workspace configuration model."""
    schema_version: str = Field(default="1.0", description="Workspace schema version")

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs):
        if isinstance(obj, dict) and "schema_version" in obj:
            obj = dict(obj)
            obj["schema_version"] = str(obj["schema_version"])
        return super().model_validate(obj, *args, **kwargs)
    name: str = Field(default="runport-workspace", description="Human-readable workspace or project name")
    budget: BudgetConfig = Field(default_factory=BudgetConfig, description="Spend limits and policies")
    approver: ApproverConfig = Field(default_factory=ApproverConfig, description="Approval mechanism settings")
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig, description="Telemetry and privacy safeguards")
    storage: StorageConfig = Field(default_factory=StorageConfig, description="Storage paths and database config")
    catalog_sources: List[str] = Field(
        default_factory=list,
        description="Paths to JSON/YAML model catalogs or plugin references",
    )
    targets: List[TargetConfig] = Field(
        default_factory=list,
        description="Configured target systems and workflow endpoints",
    )


DEFAULT_WORKSPACE_FILENAMES = ["runport.yaml", "runport.yml", "workbench.yaml", "workbench.yml"]


def find_workspace_file(root_dir: Optional[Path] = None) -> Optional[Path]:
    """Search for workspace configuration file in current or specified directory."""
    root = root_dir or Path.cwd()
    for name in DEFAULT_WORKSPACE_FILENAMES:
        p = root / name
        if p.is_file():
            return p
    return None


def load_workspace_config(path: Optional[Path] = None) -> WorkspaceConfig:
    """Load and validate workspace configuration from YAML/JSON file or defaults."""
    target_path = path or find_workspace_file()
    if target_path is None or not target_path.is_file():
        return WorkspaceConfig()

    content = target_path.read_text(encoding="utf-8")
    
    # Try parsing as JSON first, then YAML via custom parser or simple key-value/json
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(content)
        except ImportError:
            # Simple fallback parser for basic YAML if PyYAML is not installed
            data = _parse_simple_yaml(content)

    return WorkspaceConfig.model_validate(data or {})


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Minimal YAML parser fallback for basic key-value workspace configs."""
    result: Dict[str, Any] = {}
    current_section = result
    section_name = ""

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not ":" in line[:-1]:
            section_name = line[:-1].strip()
            result[section_name] = {}
            current_section = result[section_name]
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            val: Any = v
            if v.lower() == "true":
                val = True
            elif v.lower() == "false":
                val = False
            elif v.isdigit():
                val = int(v)
            elif _is_float(v):
                val = float(v)
            elif not v:
                val = None
            if section_name and current_section is not result:
                current_section[k] = val
            else:
                result[k] = val
    return result


def _is_float(val: str) -> bool:
    try:
        float(val)
        return True
    except ValueError:
        return False


def generate_workspace_schema() -> Dict[str, Any]:
    """Generate the JSON Schema for Runport workspace configuration."""
    return WorkspaceConfig.model_json_schema()


def init_workspace(
    target_dir: Path,
    name: str = "runport-workspace",
    force: bool = False,
) -> Path:
    """Initialize a new Runport workspace with directories and runport.yaml template."""
    config_path = target_dir / "runport.yaml"
    if config_path.exists() and not force:
        raise FileExistsError(f"Workspace configuration already exists at {config_path}")

    # Ensure required directories exist
    (target_dir / "data" / "evaluation").mkdir(parents=True, exist_ok=True)
    (target_dir / "reports").mkdir(parents=True, exist_ok=True)

    yaml_template = f"""# Runport Workspace Configuration
schema_version: "1.0"
name: "{name}"

budget:
  total_usd: 5.00
  per_run_usd: 1.00
  per_case_usd: 0.05
  pilot_usd: 1.00
  require_priced: false
  retry_buffer_pct: 0.05

approver:
  default_mode: "interactive"
  token_approver_enabled: false

telemetry:
  local_logging: true
  redact_secrets: true
  forbidden_fields:
    - "user4"
    - "phone"
    - "email"
    - "ssn"
    - "national_id"

storage:
  data_dir: "data"
  db_filename: "runport.db"
  reports_dir: "reports"

catalog_sources: []

targets: []
"""
    config_path.write_text(yaml_template, encoding="utf-8")
    return config_path
