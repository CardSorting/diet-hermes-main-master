#!/usr/bin/env python3
import json
import subprocess
import os
import sys

def run_joy_audit():
    """Run the JoyZoning audit and display the report."""
    print("\n🛰️  JOY-ZONING SOVEREIGN RADAR")
    print("===============================")
    
    try:
        # Use the already configured tool logic
        cmd = ["npx", "-y", "tsx", "broccolidb/cli/index.ts", "audit"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Audit failed: {result.stderr or result.stdout}")
            sys.exit(1)
            
        print(result.stdout)
        
        if "VIOLATIONS" in result.stdout:
            print("\n🚫 Structural integrity compromised. Healing required.")
            sys.exit(1)
        else:
            print("\n💎 System core is Sovereign.")
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Error executing audit: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_joy_audit()
