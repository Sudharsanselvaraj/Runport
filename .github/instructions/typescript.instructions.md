---
applyTo: "packages/sdk-ts/**,web/**"
---
# TypeScript & SDK Compatibility Instructions

Apply these rules when authoring or reviewing TypeScript and frontend code:

1. **Node 22+ Compatibility**:
   - The TypeScript SDK (`packages/sdk-ts`) runs under Node.js 22+ native `--experimental-strip-types`.
   - Do not add build scripts or options that rely on external transpilers or break native Node 22 execution.

2. **API Contract Parity**:
   - SDK models and interfaces must match the Python backend models defined in `src/runport/api/v1/models/`.
   - Maintain contract parity with the Python SDK (`src/runport_sdk/`).

3. **Strict Nullability & Types**:
   - Never default missing metrics (`cost`, `tokens`, `latency`) to 0; represent them faithfully as `null | undefined`.
   - Enforce strict typing with zero `any` usage in public SDK signatures.

4. **Error Handling & Headers**:
   - Propagate problem details and server error responses clearly to SDK callers.
   - Support authorization bearer tokens and tenant header propagation.
