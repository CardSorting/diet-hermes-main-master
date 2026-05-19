import json
import subprocess
import os
from tools.registry import registry

def check_requirements() -> bool:
    return os.path.exists("broccolidb/package.json")

def _run_broccolidb(args: list) -> str:
    # Use npx tsx to run the CLI directly from source for maximum fidelity
    try:
        # Pass GEMINI_API_KEY if available in env
        env = os.environ.copy()
        cmd = ["npx", "-y", "tsx", "broccolidb/cli/index.ts"] + args
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr or e.stdout or str(e)}"

def broccolidb_init(api_key: str = None, task_id: str = None) -> str:
    """Initialize and index the current repository with BroccoliDB."""
    # This might be interactive, so we should try to run it non-interactively if possible.
    # But the current init implementation asks for API key.
    # We'll pass it via env if provided.
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
    
    # We might need to pipe 'y' to the integration question.
    try:
        cmd = ["npx", "-y", "tsx", "broccolidb/cli/index.ts", "init"]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # We can try to send 'n' to the "Automatically add BroccoliDB to Claude Desktop?" question
        stdout, stderr = process.communicate(input="n\n")
        return json.dumps({"success": True, "output": stdout, "error": stderr})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def broccolidb_audit(task_id: str = None) -> str:
    """Perform a deep forensic audit of the codebase using BroccoliDB."""
    output = _run_broccolidb(["audit"])
    return json.dumps({"success": True, "output": output})

def broccolidb_refactor(file_path: str, action: str, task_id: str = None) -> str:
    """Generate a mission-focused refactoring manifest for a file."""
    output = _run_broccolidb(["refactor", file_path, action])
    return json.dumps({"success": True, "output": output})

def broccolidb_status(task_id: str = None) -> str:
    """View the health and stats of the Context Graph."""
    output = _run_broccolidb(["status"])
    return json.dumps({"success": True, "output": output})

def broccolidb_joyzoning_audit(task_id: str = None) -> str:
    """Perform a deep forensic audit of the codebase to identify structural violations."""
    # This specifically targets JoyZoning rules
    output = _run_broccolidb(["audit"])
    return json.dumps({"success": True, "output": output})

def broccolidb_joyzoning_refactor(file_path: str, action: str, task_id: str = None) -> str:
    """Generate a mission-focused refactoring manifest for a file."""
    output = _run_broccolidb(["refactor", file_path, action])
    return json.dumps({"success": True, "output": output})

registry.register(
    name="broccolidb_init",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_init",
        "description": "Initialize and index the current repository with BroccoliDB to enable forensic structural analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Optional Gemini API Key for semantic search features"}
            }
        }
    },
    handler=lambda args, **kw: broccolidb_init(api_key=args.get("api_key"), task_id=kw.get("task_id")),
    check_fn=check_requirements,
)

registry.register(
    name="broccolidb_audit",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_audit",
        "description": "Perform a deep forensic audit of the codebase to identify structural violations, technical debt, and architectural drift.",
        "parameters": {"type": "object", "properties": {}}
    },
    handler=lambda args, **kw: broccolidb_audit(task_id=kw.get("task_id")),
    check_fn=check_requirements,
)

registry.register(
    name="broccolidb_refactor",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_refactor",
        "description": "Generate a specific mission-focused refactoring manifest for a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to refactor"},
                "action": {
                    "type": "string", 
                    "enum": ["DECOMPOSE", "MOVE", "EXTRACT", "PRUNE", "ALIGN_TAGS", "HEAL_STATELESSNESS", "HARDEN", "DECOUPLE", "FIX_STRUCTURAL_VIOLATION"],
                    "description": "The refactoring action to perform"
                }
            },
            "required": ["file_path", "action"]
        }
    },
    handler=lambda args, **kw: broccolidb_refactor(file_path=args.get("file_path"), action=args.get("action"), task_id=kw.get("task_id")),
    check_fn=check_requirements,
)

registry.register(
    name="broccolidb_status",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_status",
        "description": "View the health and stats of the BroccoliDB Context Graph.",
        "parameters": {"type": "object", "properties": {}}
    },
    handler=lambda args, **kw: broccolidb_status(task_id=kw.get("task_id")),
    check_fn=check_requirements,
)

registry.register(
    name="broccolidb_joyzoning_audit",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_joyzoning_audit",
        "description": "Perform a deep forensic audit of the codebase to identify structural violations, technical debt, and architectural drift.",
        "parameters": {"type": "object", "properties": {}}
    },
    handler=lambda args, **kw: broccolidb_joyzoning_audit(task_id=kw.get("task_id")),
    check_fn=check_requirements,
)

registry.register(
    name="broccolidb_joyzoning_refactor",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_joyzoning_refactor",
        "description": "Generate a specific mission-focused refactoring manifest for a file or batch of files.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to refactor"},
                "action": {
                    "type": "string", 
                    "enum": ["DECOMPOSE", "MOVE", "EXTRACT", "PRUNE", "ALIGN_TAGS", "HEAL_STATELESSNESS", "HARDEN", "DECOUPLE", "FIX_STRUCTURAL_VIOLATION"],
                    "description": "The refactoring action to perform"
                }
            },
            "required": ["file_path", "action"]
        }
    },
    handler=lambda args, **kw: broccolidb_joyzoning_refactor(file_path=args.get("file_path"), action=args.get("action"), task_id=kw.get("task_id")),
    check_fn=check_requirements,
)
