import sys
import json
import os
import io

# Add hermes to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))
from run_agent import AIAgent
from tools.registry import registry
from toolsets import _HERMES_CORE_TOOLS

def main():
    input_data = sys.stdin.read()
    if not input_data:
        return
        
    try:
        data = json.loads(input_data)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}))
        return

    prompt = data.get("prompt", "")
    files = data.get("files", [])
    history = data.get("history", [])

    # Stub out reality-touching tools
    # We do this by replacing the handler in the registry for specific tools
    proposals = []

    def mock_run_command(args, **kwargs):
        proposals.append({
            "action": "propose_command",
            "command": args.get("command"),
            "cwd": args.get("cwd", "."),
            "reason": args.get("reason", "Running command")
        })
        return json.dumps({"success": True, "message": "Command proposed for execution. It has not executed yet, waiting for user approval."})

    def mock_write_file(args, **kwargs):
        proposals.append({
            "action": "propose_patch",
            "path": args.get("path"),
            "diff": args.get("content"),
            "reason": "Writing file"
        })
        return json.dumps({"success": True, "message": "File write proposed."})

    def mock_replace_file_content(args, **kwargs):
        proposals.append({
            "action": "propose_patch",
            "path": args.get("path"),
            "diff": args.get("replacementContent"),
            "reason": "Replacing file content"
        })
        return json.dumps({"success": True, "message": "File replace proposed."})

    def mock_view_file(args, **kwargs):
        # We should ask for context.request
        path = args.get("path", "")
        proposals.append({
            "action": "request_context",
            "paths": [path],
            "reason": "Need to view file"
        })
        return json.dumps({"success": True, "message": "Requested file from local context. Please wait."})

    # Find and mock the tools in registry
    for name, tool_def in registry.tools.items():
        if name in ['run_command', 'run_command_background']:
            tool_def.handler = mock_run_command
        elif name in ['write_to_file', 'create_file']:
            tool_def.handler = mock_write_file
        elif name in ['replace_file_content']:
            tool_def.handler = mock_replace_file_content
        elif name in ['view_file', 'read_file']:
            tool_def.handler = mock_view_file
            
    # Also we want to ensure we don't actually output stdout garbage
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    agent = AIAgent(
        model="gpt-4o",
        api_mode="chat_completions",
        enabled_toolsets=["core"], 
        quiet_mode=True,
        max_iterations=1 # Limit to 1 for POC so it doesn't loop
    )

    context_str = "Available files:\n"
    for f in files:
        context_str += f"--- {f.get('path')} ---\n{f.get('content')}\n"

    transcript_str = "Session Transcript:\n"
    for h in history:
        role = h.get("role", "unknown").upper()
        content = h.get("content", "")
        transcript_str += f"[{role}]: {content}\n"

    system_prompt = f"You are Hermes running in a remote sandbox. You cannot run commands directly or edit files directly. Use your tools to propose changes.\n\n{transcript_str}\n\nContext:\n{context_str}"

    try:
        res = agent.run_conversation(user_message=prompt, system_message=system_prompt)
        sys.stdout = old_stdout
        
        # Output the collected proposals or the final text
        if proposals:
            print(json.dumps({"decisions": proposals}))
        else:
            print(json.dumps({"decisions": [{"action": "transcript", "text": res.get("final_response", "")}]}))
    except Exception as e:
        sys.stdout = old_stdout
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
