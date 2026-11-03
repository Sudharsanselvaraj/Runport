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
        default_factory=lambda: ["restricted_user_id", "phone", "email", "ssn", "national_id"],
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
    root_dir: Optional[Path] = Field(default=None, description="Anchored workspace root directory")
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


def _check_no_secrets(data: Any, path: str = "") -> None:
    """Invariant: API keys, bearer tokens, and credentials must NEVER be committed to YAML files."""
    forbidden_keys = {"api_key", "secret", "private_key", "password", "access_token"}
    safe_exceptions = {
        "token_approver_enabled", "redact_secrets", "est_prompt_tokens",
        "est_completion_tokens", "context_length", "tokens_in", "tokens_out",
        "max_tokens", "prompt_tokens", "completion_tokens"
    }
    if isinstance(data, dict):
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in forbidden_keys) and k_lower not in safe_exceptions:
                if isinstance(v, str) and not v.startswith("$"):
                    raise ValueError(
                        f"Secret or API key detected in workspace configuration ('{path}{k}'). "
                        "API keys must never be committed to YAML files; use environment variables instead."
                    )
            _check_no_secrets(v, f"{path}{k}.")
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            _check_no_secrets(item, f"{path}[{idx}].")


def find_workspace_file(root_dir: Optional[Path] = None) -> Optional[Path]:
    """Search for workspace configuration file in current or specified directory."""
    root = root_dir or Path.cwd()
    for name in DEFAULT_WORKSPACE_FILENAMES:
        p = root / name
        if p.is_file():
            return p
    return None


def load_workspace_config(path: Optional[Path] = None) -> WorkspaceConfig:
    """Load and validate workspace configuration from YAML/JSON file or defaults.
    
    All storage and dataset paths are anchored to target_path.parent, independent of CWD.
    API keys and bearer tokens are strictly forbidden from YAML content.
    """
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

    _check_no_secrets(data or {})

    cfg = WorkspaceConfig.model_validate(data or {})
    base_dir = target_path.parent.resolve()
    cfg.root_dir = base_dir
    # Anchor storage paths relative to workspace config location (independent of CWD)
    if not cfg.storage.data_dir.is_absolute():
        cfg.storage.data_dir = (base_dir / cfg.storage.data_dir).resolve()
    if not cfg.storage.reports_dir.is_absolute():
        cfg.storage.reports_dir = (base_dir / cfg.storage.reports_dir).resolve()
    return cfg


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """YAML parser for workspace configurations without external dependencies."""
    result: Dict[str, Any] = {}
    # stack entry: [indent, container, key_in_parent, parent_container]
    stack: List[List[Any]] = [[-1, result, None, None]]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        line = raw_line.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        parent_indent, parent_container, parent_key, grandparent_container = stack[-1]

        if line.startswith("- "):
            val_part = line[2:].strip()
            # If current parent is an empty dict created for a section, convert it to a list
            if isinstance(parent_container, dict) and len(parent_container) == 0 and grandparent_container is not None and parent_key is not None:
                new_list: List[Any] = []
                grandparent_container[parent_key] = new_list
                parent_container = new_list
                stack[-1][1] = new_list

            if isinstance(parent_container, list):
                target_list = parent_container
            elif isinstance(parent_container, dict):
                if parent_key and not isinstance(parent_container.get(parent_key), list):
                    parent_container[parent_key] = []
                target_list = parent_container[parent_key] if parent_key else []
            else:
                target_list = []

            if ":" in val_part:
                k, v = val_part.split(":", 1)
                item_dict = {k.strip(): _parse_val(v.strip())}
                target_list.append(item_dict)
                stack.append([indent, item_dict, None, target_list])
            else:
                target_list.append(_parse_val(val_part))
            continue

        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()

            if not v:
                new_dict: Dict[str, Any] = {}
                if isinstance(parent_container, dict):
                    parent_container[k] = new_dict
                stack.append([indent, new_dict, k, parent_container])
            else:
                parsed_v = _parse_val(v)
                if isinstance(parent_container, dict):
                    parent_container[k] = parsed_v
                stack.append([indent, parent_container, k, grandparent_container])

    return result


def _parse_val(v: str) -> Any:
    v = v.strip().strip("'\"")
    if v.startswith("[") and v.endswith("]"):
        try:
            return json.loads(v)
        except Exception:
            return [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.isdigit():
        return int(v)
    if _is_float(v):
        return float(v)
    if not v:
        return None
    return v


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
    - "restricted_user_id"
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
