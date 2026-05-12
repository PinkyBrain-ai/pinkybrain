================================================================
  PinkyBrain — shared_models/ SHARING ZONE
================================================================

This directory is the ONLY location visible to the public
PinkyBrain P2P network.

  ✅  Models placed HERE are discoverable by other nodes.
  ❌  Cloud models (OpenAI, Anthropic, etc.) using your API
      keys are NOT shared by default. Sharing requires explicit
      force=True + a cost warning.

HOW IT WORKS:
- Any model file or folder you place in this directory
  will be advertised to the mesh and available for other
  nodes to query.
- Cloud-hosted models that use your personal API keys
  (e.g., GPT-4, Claude) remain private by default, even
  if you have configured them in PinkyBrain.
- To explicitly share a cloud model, you must set
  force=True on that model's configuration. Think carefully
  before doing this — it means other nodes can use your
  API keys.

RECOMMENDED:
- Share local/open-weight models (GGUF, safetensors, etc.)
- Keep cloud models private unless you understand the
  cost implications.

For more info: https://github.com/PinkyBrain-ai/pinkybrain
================================================================