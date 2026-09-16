import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from managed.control import initial
from managed.store import Store


@unittest.skipUnless(shutil.which("node"), "Node is required for the managed bridge tests")
class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "company"
        state = initial(json.loads((ROOT/"managed/company.example.json").read_text()))
        state.update(ready=True,gateway_pending=False)
        state["people"]["+12025550103"] = {"name":"Ana","active":True,"resources":{}}
        self.store = Store(self.root)
        self.store.initialize(state)
        self.config = {"root":str(self.root),"release":str(ROOT),"python":sys.executable}

    def node(self, body):
        source = 'import {createBridge,toolActor} from ' + json.dumps((ROOT/'runtimes/openclaw/plugins/puestario-control/bridge.js').as_uri()) + ';\n'
        source += 'const config = ' + json.dumps(self.config) + ';\n'
        source += '''const ctx={messageChannel:"whatsapp",agentAccountId:"default",sessionId:"test-session",requesterSenderId:"+12025550103",
            deliveryContext:{channel:"whatsapp",accountId:"default",to:"+12025550103"}};\n'''+body
        result = subprocess.run(["node","--input-type=module","-e",source],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_real_python_bridge_staff_status_and_founder_denial(self):
        result = self.node('''const bridge=createBridge(config); const tool=bridge.tool(ctx);
          const status=await tool.execute("one",{operation:"status",args:{}});
          const admin=await tool.execute("two",{operation:"setup.open",args:{asked_by:"+12025550101"}});
          console.log(JSON.stringify({status,admin}));''')
        self.assertTrue(result["status"]["details"]["ok"])
        self.assertTrue(result["admin"]["isError"])
        self.assertIsNone(self.store.read()["setup"])

    def test_no_tool_for_missing_or_mismatched_identity(self):
        result=self.node('''const bridge=createBridge(config); console.log(JSON.stringify([
          bridge.tool({...ctx,requesterSenderId:undefined}),bridge.tool({...ctx,agentAccountId:undefined}),
          bridge.tool({...ctx,deliveryContext:{...ctx.deliveryContext,accountId:"different"}})]));''')
        self.assertEqual(result,[None,None,None])

    def test_model_cannot_supply_actor_or_unknown_operation(self):
        result=self.node('''let calls=0; const bridge=createBridge(config,async()=>{calls++; return {}}); const tool=bridge.tool(ctx);
          const forged=await tool.execute("one",{operation:"setup.open",args:{},actor:{sender:"+12025550101"}});
          const shell=await tool.execute("two",{operation:"exec",args:{command:"anything"}});
          console.log(JSON.stringify({calls,forged,shell}));''')
        self.assertEqual(result["calls"],0)
        self.assertTrue(result["forged"]["isError"])
        self.assertTrue(result["shell"]["isError"])

    def test_gate_requires_trusted_factory_context(self):
        result=self.node('''const bridge=createBridge(config); const event={senderId:ctx.requesterSenderId,channelId:"whatsapp",accountId:"default",messages:[]};
          const absent=await bridge.beforeRun(event,{sessionId:ctx.sessionId,runId:"run"});
          bridge.tool(ctx);
          const present=await bridge.beforeRun(event,{sessionId:ctx.sessionId,runId:"run"});
          const wrong=await bridge.beforeRun({...event,senderId:"+12025550101"},{sessionId:ctx.sessionId,runId:"run"});
          console.log(JSON.stringify({absent,present,wrong}));''')
        self.assertEqual(result["absent"]["outcome"],"block")
        self.assertEqual(result["present"]["outcome"],"pass")
        self.assertEqual(result["wrong"]["outcome"],"block")

    def test_ungated_outbound_unknown_target_and_arbitrary_tool_blocked(self):
        result=self.node('''const bridge=createBridge(config); console.log(JSON.stringify({
          send:bridge.sending({to:"+12025550103",content:"private"},{channelId:"whatsapp",accountId:"default"}),
          unknown:bridge.sending({to:"+12025550199",content:"private"},{channelId:"whatsapp",accountId:"default"}),
          tool:bridge.beforeTool({toolName:"exec"})}));''')
        self.assertTrue(result["send"]["cancel"])
        self.assertTrue(result["unknown"]["cancel"])
        self.assertTrue(result["tool"]["block"])

    def test_approved_run_can_reply_only_to_its_conversation(self):
        result=self.node('''const bridge=createBridge(config); bridge.tool(ctx);
          await bridge.beforeRun({senderId:ctx.requesterSenderId,channelId:"whatsapp",accountId:"default",messages:[]},{sessionId:ctx.sessionId,runId:"run"});
          console.log(JSON.stringify({own:bridge.sending({to:ctx.requesterSenderId,content:"ok"},{channelId:"whatsapp",accountId:"default",runId:"run"})??null,
          other:bridge.sending({to:"+12025550101",content:"private"},{channelId:"whatsapp",accountId:"default",runId:"run"})}));''')
        self.assertIsNone(result["own"])
        self.assertTrue(result["other"]["cancel"])

    def test_reply_without_transport_run_id_requires_exact_approved_output(self):
        result=self.node('''const bridge=createBridge(config); bridge.tool(ctx);
          await bridge.beforeRun({senderId:ctx.requesterSenderId,channelId:"whatsapp",accountId:"default",messages:[]},{sessionId:ctx.sessionId,runId:"run"});
          bridge.output({runId:"run",assistantTexts:["Approved reply"]},{});
          const channel={channelId:"whatsapp",accountId:"default"};
          console.log(JSON.stringify({ok:bridge.sending({to:ctx.requesterSenderId,content:"Approved reply"},channel)??null,
          forged:bridge.sending({to:ctx.requesterSenderId,content:"Different private reply"},channel)}));''')
        self.assertIsNone(result["ok"])
        self.assertTrue(result["forged"]["cancel"])

    def test_revocation_blocks_inflight_reply_even_when_original_run_passed(self):
        result=self.node('''const {writeFileSync,readFileSync}=await import("node:fs");
          const bridge=createBridge(config); bridge.tool(ctx);
          await bridge.beforeRun({senderId:ctx.requesterSenderId,channelId:"whatsapp",accountId:"default",messages:[]},{sessionId:ctx.sessionId,runId:"run"});
          bridge.output({runId:"run",assistantTexts:["Approved reply"]},{});
          const state=JSON.parse(readFileSync(config.root+"/control.json")); state.access_epoch=1;
          writeFileSync(config.root+"/control.json",JSON.stringify(state));
          console.log(JSON.stringify(bridge.sending({to:ctx.requesterSenderId,content:"Approved reply"},{channelId:"whatsapp",accountId:"default"})));''')
        self.assertTrue(result["cancel"])

    def test_named_test_member_can_receive_group_reply_during_setup(self):
        with self.store.locked() as state:
            state.update(ready=False,setup={"owner":"+12025550101","until":4102444800})
            state["people"]["+12025550103"]["tester"]=True
            state["groups"]["1234567890@g.us"]={"name":"Test","members":["+12025550103"],"resources":{}}
        result=self.node('''ctx.deliveryContext.to="1234567890@g.us";
          const bridge=createBridge(config); bridge.tool(ctx);
          const gate=await bridge.beforeRun({senderId:ctx.requesterSenderId,channelId:"whatsapp",accountId:"default",messages:[]},{sessionId:ctx.sessionId,runId:"run"});
          bridge.output({runId:"run",assistantTexts:["Group test"]},{});
          console.log(JSON.stringify({gate,send:bridge.sending({to:ctx.deliveryContext.to,content:"Group test"},{channelId:"whatsapp",accountId:"default"})??null}));''')
        self.assertEqual(result["gate"]["outcome"],"pass")
        self.assertIsNone(result["send"])

    def test_fresh_runtime_context_is_not_old_conversation_history(self):
        result=self.node('''const bridge=createBridge(config); bridge.tool(ctx);
          console.log(JSON.stringify(await bridge.beforeRun({senderId:ctx.requesterSenderId,channelId:"whatsapp",accountId:"default",
          messages:[{role:"custom",customType:"openclaw.runtime-context",details:{source:"openclaw-runtime-context"}}]},
          {sessionId:ctx.sessionId,runId:"run"})));''')
        self.assertEqual(result["outcome"],"pass")


if __name__ == "__main__": unittest.main()
