#!/usr/bin/env python3
"""
[LAYER: PLUMBING]

Joy-Zoning Sovereign Radar CLI.
A pure Python CLI to perform a global or target-specific architectural health audit.
Bypasses Node.js binary compilation issues and runs natively.
"""

import os
import sys
import argparse

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.joy_zoning import get_layer, find_workspace_root
from agent.governance_exemptions import (
    _joy_zoning_validate,
    iter_governance_subject_files,
)

def run_joy_audit():
    parser = argparse.ArgumentParser(description="Joy-Zoning Sovereign Radar CLI")
    parser.add_argument("paths", nargs="*", help="Specific files or directories to scan. Defaults to workspace walk.")
    parser.add_argument("--strict", action="store_true", help="Fail on missing tags for all files. Otherwise, missing tags only fail under agent/, tools/, and broccolidb/.")
    args = parser.parse_args()

    root = find_workspace_root(__file__)
    print(f"\n🛰️  JOY-ZONING SOVEREIGN RADAR (Python Engine)")
    print(f"Project Root: {root}")
    print("==============================================")
    
    layers_files = {
        "domain": [],
        "core": [],
        "infrastructure": [],
        "plumbing": [],
        "ui": []
    }
    
    all_violations = []
    all_warnings = []
    
    # Excluded directories for speed and isolation
    exclude_dirs = {
        "node_modules", ".venv", "venv", "tests", ".git", ".github",
        "dist", "build", "website", ".plans", ".pytest_cache"
    }
    
    # Collect files to scan
    files_to_scan = []
    if args.paths:
        for p in args.paths:
            abs_p = os.path.abspath(p)
            if not os.path.exists(abs_p):
                print(f"⚠️  Path not found: {p}")
                continue
            if os.path.isfile(abs_p):
                files_to_scan.append(abs_p)
            else:
                for dirpath, dirnames, filenames in os.walk(abs_p):
                    dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
                    for filename in filenames:
                        files_to_scan.append(os.path.join(dirpath, filename))
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
            for filename in filenames:
                files_to_scan.append(os.path.join(dirpath, filename))

    validate_fn = _joy_zoning_validate()
    for full_path, content in iter_governance_subject_files(files_to_scan):
        rel_path = os.path.relpath(full_path, root).replace("\\", "/")
        if os.path.basename(full_path).startswith("."):
            continue

        layer = get_layer(full_path, content)
        if layer in layers_files:
            layers_files[layer].append(rel_path)

        audit = validate_fn(full_path, content, skip_subject_check=True)
        if not audit["success"]:
            for err in audit["errors"]:
                is_missing_tag = "Missing mandatory [LAYER: TYPE] header tag" in err
                if is_missing_tag:
                    is_core_dir = any(
                        rel_path.startswith(prefix)
                        for prefix in ("agent/", "tools/", "broccolidb/")
                    )
                    if is_core_dir or args.strict:
                        all_violations.append((rel_path, err))
                    else:
                        all_warnings.append((rel_path, err))
                else:
                    all_violations.append((rel_path, err))

    # Display layer summaries
    layers = ["domain", "core", "infrastructure", "plumbing", "ui"]
    
    for layer in layers:
        files = layers_files[layer]
        layer_violations = [v for v in all_violations if get_layer(os.path.join(root, v[0])) == layer]
        layer_warnings = [w for w in all_warnings if get_layer(os.path.join(root, w[0])) == layer]
        
        status = "✅ STABLE"
        if len(layer_violations) > 0:
            status = "🚨 FEVER"
        elif len(layer_warnings) > 0:
            status = "⚠️  DEGRADED"
            
        print(f"\n[{layer.upper()}] status: {status}")
        print(f"- Files detected: {len(files)}")
        print(f"- Violations: {len(layer_violations)}")
        if len(layer_warnings) > 0:
            print(f"- Warnings (legacy missing tags): {len(layer_warnings)}")

    if all_warnings:
        print(f"\n⚠️  LEGACY WARNINGS ({len(all_warnings)} untagged files):")
        # limit warnings display to 10
        for path, msg in all_warnings[:10]:
            print(f"  - {path}: {msg}")
        if len(all_warnings) > 10:
            print(f"  ... and {len(all_warnings) - 10} more warnings.")

    if all_violations:
        print(f"\n❌ CRITICAL VIOLATIONS DETECTED ({len(all_violations)}):")
        for path, msg in all_violations:
            print(f"  - {path}: {msg}")
            
        print("\n🚫 Structural integrity compromised. Healing required.")
        sys.exit(1)
    else:
        print("\n💎 System core is Sovereign.")
        sys.exit(0)

if __name__ == "__main__":
    run_joy_audit()
