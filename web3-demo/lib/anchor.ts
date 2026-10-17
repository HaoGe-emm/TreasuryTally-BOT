import { createPublicClient, http, parseAbi, type Address, type Hex } from "viem";
import { botChain } from "./chain";

export const anchorAbi = parseAbi([
  "function tasks(address requester, bytes32 taskDigest) view returns (address requesterStored, address serviceSigner)",
  "function delivered(address requester, bytes32 taskDigest, uint8 attempt) view returns (bool)",
  "function anchorTask(bytes32 taskDigest, bytes32 specHash, bytes32 serviceIdHash, address serviceSigner)",
  "function anchorDelivery(address requester, bytes32 taskDigest, uint8 attempt, bytes32 submissionIdHash, bytes32 reportHash, bytes32 deliveryDigest)",
  "event TaskAnchored(bytes32 indexed taskDigest, address indexed requester, address indexed serviceSigner, bytes32 specHash, bytes32 serviceIdHash)",
  "event DeliveryAnchored(bytes32 indexed taskDigest, address indexed serviceSigner, uint8 indexed attempt, address requester, bytes32 submissionIdHash, bytes32 reportHash, bytes32 deliveryDigest)"
]);

export const publicClient = createPublicClient({
  chain: botChain, transport: http(undefined, { timeout: 12_000, retryCount: 1 })
});

// Public, fixed deployment verified in Stage 3C. Production reads must not rely
// on a developer's .env.local or silently point to another contract.
export const anchorAddress: Address = "0xAf845BA2D1aF0e842FD2185fa081720D6D3D7148";
export const anchorRuntimeHash: Hex = "0xe19c6b11680cbd60c5fb6061d52052c65596e48b9c10cbc59415538e03a75eaf";
