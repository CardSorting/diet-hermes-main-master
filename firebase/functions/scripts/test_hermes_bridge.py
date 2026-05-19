import unittest
import json
import sys
import io
from unittest.mock import patch

# Import the module to test
import hermes_bridge

class TestHermesBridge(unittest.TestCase):
    def run_bridge_with_input(self, input_data: dict, mock_agent_behavior):
        # Setup stdin and stdout
        original_stdin = sys.stdin
        original_stdout = sys.stdout
        
        sys.stdin = io.StringIO(json.dumps(input_data))
        output_capture = io.StringIO()
        sys.stdout = output_capture
        
        try:
            with patch('hermes_bridge.AIAgent') as MockAIAgent:
                # Setup the mock agent
                mock_instance = MockAIAgent.return_value
                
                # mock_agent_behavior should simulate what AIAgent would do (i.e. call a tool)
                def side_effect(user_message, system_message):
                    mock_agent_behavior()
                    return {"final_response": "Done"}
                    
                mock_instance.run_conversation.side_effect = side_effect
                
                # Run the bridge
                hermes_bridge.main()
                
                # Get and parse output
                output_capture.seek(0)
                output_str = output_capture.read().strip()
                try:
                    return json.loads(output_str)
                except json.JSONDecodeError:
                    return {"raw_output": output_str}
        finally:
            sys.stdin = original_stdin
            sys.stdout = original_stdout

    def test_hermes_attempts_file_write(self):
        # 1. Hermes attempts file write -> must become proposal.patch, no cloud file mutation
        def behavior():
            # Find the mocked tool in registry
            from tools.registry import registry
            tool = registry.tools['write_to_file']
            tool.handler({"path": "test.txt", "content": "hello world"})
            
        result = self.run_bridge_with_input({"prompt": "write a file"}, behavior)
        
        self.assertIn("decisions", result)
        decisions = result["decisions"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["action"], "propose_patch")
        self.assertEqual(decisions[0]["path"], "test.txt")
        self.assertEqual(decisions[0]["diff"], "hello world")

    def test_hermes_attempts_shell_command(self):
        # 2. Hermes attempts shell command -> must become proposal.command, no cloud command execution
        def behavior():
            from tools.registry import registry
            tool = registry.tools['run_command']
            tool.handler({"command": "echo hello", "cwd": "/tmp"})
            
        result = self.run_bridge_with_input({"prompt": "run a command"}, behavior)
        
        decisions = result["decisions"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["action"], "propose_command")
        self.assertEqual(decisions[0]["command"], "echo hello")
        self.assertEqual(decisions[0]["cwd"], "/tmp")

    def test_hermes_requests_file(self):
        # 3. Hermes requests file -> must become context.request
        def behavior():
            from tools.registry import registry
            tool = registry.tools['view_file']
            tool.handler({"path": "package.json"})
            
        result = self.run_bridge_with_input({"prompt": "view a file"}, behavior)
        
        decisions = result["decisions"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["action"], "request_context")
        self.assertEqual(decisions[0]["paths"], ["package.json"])

    def test_hermes_emits_final_answer(self):
        # 4. Hermes emits final answer -> must become stream.transcript
        def behavior():
            # Does not call any tools
            pass
            
        result = self.run_bridge_with_input({"prompt": "hello"}, behavior)
        
        decisions = result["decisions"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["action"], "transcript")
        self.assertEqual(decisions[0]["text"], "Done")

    def test_hermes_bridge_crashes(self):
        # 5. Hermes bridge crashes -> must become session.error
        # We simulate a crash by making run_conversation raise an exception
        original_stdin = sys.stdin
        original_stdout = sys.stdout
        sys.stdin = io.StringIO(json.dumps({"prompt": "crash"}))
        output_capture = io.StringIO()
        sys.stdout = output_capture
        
        try:
            with patch('hermes_bridge.AIAgent') as MockAIAgent:
                mock_instance = MockAIAgent.return_value
                mock_instance.run_conversation.side_effect = Exception("Simulated crash")
                hermes_bridge.main()
                
                output_capture.seek(0)
                output_str = output_capture.read().strip()
                result = json.loads(output_str)
                
                self.assertIn("error", result)
                self.assertEqual(result["error"], "Simulated crash")
        finally:
            sys.stdin = original_stdin
            sys.stdout = original_stdout

    def test_malformed_bridge_json(self):
        # 6. Malformed bridge JSON -> must become session.error
        # The typescript adapter handles this, but here we can test the bridge's own JSON parsing
        original_stdin = sys.stdin
        original_stdout = sys.stdout
        sys.stdin = io.StringIO("not json")
        output_capture = io.StringIO()
        sys.stdout = output_capture
        
        try:
            hermes_bridge.main()
            output_capture.seek(0)
            output_str = output_capture.read().strip()
            result = json.loads(output_str)
            
            self.assertIn("error", result)
            self.assertEqual(result["error"], "Invalid JSON input")
        finally:
            sys.stdin = original_stdin
            sys.stdout = original_stdout

    def test_multiple_tool_intents(self):
        # 7. Multiple tool intents -> must serialize into multiple decisions safely
        def behavior():
            from tools.registry import registry
            tool1 = registry.tools['run_command']
            tool1.handler({"command": "ls", "cwd": "."})
            
            tool2 = registry.tools['write_to_file']
            tool2.handler({"path": "log.txt", "content": "done"})
            
        result = self.run_bridge_with_input({"prompt": "do two things"}, behavior)
        
        decisions = result["decisions"]
        self.assertEqual(len(decisions), 2)
        self.assertEqual(decisions[0]["action"], "propose_command")
        self.assertEqual(decisions[1]["action"], "propose_patch")

if __name__ == '__main__':
    unittest.main()
